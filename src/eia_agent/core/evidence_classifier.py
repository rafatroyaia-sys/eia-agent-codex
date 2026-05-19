"""
evidence_classifier -- IN-03
Clasifica entidades extraídas por IN-02 en hechos candidatos estructurados,
compatibles con la capa `hechos_confirmados.json` (NL-01).

No usa IA. No escribe en disco. No confirma administrativamente.

Uso:
    from eia_agent.core.evidence_classifier import classify_entities_from_docx

    result = classify_entities_from_docx("inputs/memorias/Doc.docx", "DOC-001")
    for f in result.by_category("residuos"):
        print(f.campo, f.valor, f.estado)
    print(result.summary())
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

from eia_agent.core.evidence_state import EvidenceState
from eia_agent.core.entity_extractor import ExtractedEntity, ExtractionResult


# ---------------------------------------------------------------------------
# Mapeo canónico: entity_type → (categoria, campo)
# ---------------------------------------------------------------------------

_ENTITY_MAP: dict[str, tuple[str, str]] = {
    "REFERENCIA_CATASTRAL": ("emplazamiento", "referencia_catastral"),
    "LER":                  ("residuos",      "codigo_ler"),
    "OPERACION":            ("operaciones",   "operacion_residuos"),
    "OPERACION_RESIDUOS":   ("operaciones",   "operacion_residuos"),
    "CAPACIDAD":            ("capacidades",   "capacidad"),
    "POTENCIA":             ("equipos",       "potencia"),
    "FECHA":                ("fechas",        "fecha_documental"),
    "PROMOTOR":             ("promotor",      "nombre_promotor"),
    "TITULAR":              ("titularidad",   "titular"),
    "EQUIPO":               ("equipos",       "equipo"),
}

# Subtipos de SUPERFICIE
_SUPERFICIE_MAP: dict[str, str] = {
    "SUPERFICIE_CONSTRUIDA": "superficie_construida",
    "SUPERFICIE_UTIL":       "superficie_util",
    "SUPERFICIE_CATASTRAL":  "superficie_catastral",
    "SUPERFICIE_PARCELA":    "superficie_parcela",
    "SUPERFICIE_NAVE":       "superficie_nave",
    "SUPERFICIE":            "superficie_no_clasificada",
}

_NOTE_ASUNCION = (
    "Dato procedente de asunción test; "
    "no apto para expediente administrativo real sin confirmación."
)
_NOTE_LOW_CONFIDENCE = (
    "Entidad detectada con confianza baja (LOW); "
    "verificar antes de usar en documento administrativo."
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CandidateFact:
    """Hecho candidato generado por el clasificador de evidencias (IN-03).

    Representa una entidad extraída ya mapeada a categoria/campo del esquema
    de hechos_confirmados. No ha sido confirmada administrativamente.
    """
    id: str | None
    categoria: str
    campo: str
    valor: object
    estado: str
    fuentes: list[str]
    entity_type: str
    confidence: str
    context: str | None = None
    normalized_value: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_hecho_confirmado(self) -> dict:
        """Devuelve dict compatible con hechos_confirmados.schema.json.

        `id` puede ser None si el hecho no ha pasado por to_hechos_confirmados().
        En ese caso el dict no será válido contra el schema (id requerido).
        """
        nota: str | None = None
        if self.notes:
            nota = " | ".join(self.notes)
        return {
            "id": self.id,
            "categoria": self.categoria,
            "campo": self.campo,
            "valor": self.valor,
            "estado": self.estado,
            "fuentes": list(self.fuentes),
            "nota": nota,
        }


@dataclass
class ClassificationResult:
    """Resultado de la clasificación de entidades de un documento."""
    facts: list[CandidateFact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)

    def by_category(self, categoria: str) -> list[CandidateFact]:
        """Devuelve hechos de la categoría indicada."""
        return [f for f in self.facts if f.categoria == categoria]

    def by_field(self, campo: str) -> list[CandidateFact]:
        """Devuelve hechos del campo indicado."""
        return [f for f in self.facts if f.campo == campo]

    def values(self, campo: str) -> list[object]:
        """Devuelve los valores de los hechos del campo indicado."""
        return [f.valor for f in self.facts if f.campo == campo]

    def summary(self) -> str:
        """Resumen de hechos candidatos por categoría."""
        if not self.facts:
            return "Sin hechos candidatos detectados."
        counts: dict[str, int] = {}
        for f in self.facts:
            counts[f.categoria] = counts.get(f.categoria, 0) + 1
        lines = [f"{c}: {n}" for c, n in sorted(counts.items())]
        total = len(self.facts)
        conf_str = f" | {len(self.conflicts)} conflicto(s)" if self.conflicts else ""
        warn_str = f" | {len(self.warnings)} aviso(s)" if self.warnings else ""
        return f"{total} hechos — " + ", ".join(lines) + conf_str + warn_str

    def to_hechos_confirmados(
        self,
        start_index: int = 1,
        prefix: str = "HC",
    ) -> list[dict]:
        """Genera lista de dicts lista para serializar como hechos_confirmados.json.

        Asigna IDs secuenciales: HC-001, HC-002... (o prefijo alternativo).
        """
        result = []
        for i, f in enumerate(self.facts, start=start_index):
            f_copy = CandidateFact(
                id=f"{prefix}-{i:03d}",
                categoria=f.categoria,
                campo=f.campo,
                valor=f.valor,
                estado=f.estado,
                fuentes=f.fuentes,
                entity_type=f.entity_type,
                confidence=f.confidence,
                context=f.context,
                normalized_value=f.normalized_value,
                notes=list(f.notes),
            )
            result.append(f_copy.to_hecho_confirmado())
        return result


# ---------------------------------------------------------------------------
# Clasificación interna por tipo de entidad
# ---------------------------------------------------------------------------

def _resolve_categoria_campo(entity: ExtractedEntity) -> tuple[str, str]:
    """Devuelve (categoria, campo) para una entidad dada."""
    et = entity.entity_type

    # Coordenadas: distinguir WGS84 vs UTM por normalized_value
    if et == "COORDENADA":
        nv = (entity.normalized_value or "").upper()
        if nv.startswith("DEC"):
            return ("emplazamiento", "coordenadas_wgs84")
        if nv.startswith("UTM"):
            return ("emplazamiento", "coordenadas_utm")
        return ("emplazamiento", "coordenadas")

    # Superficies: subtipos ya embebidos en entity_type
    if et in _SUPERFICIE_MAP:
        return ("superficies", _SUPERFICIE_MAP[et])

    # Resto del mapeo canónico
    if et in _ENTITY_MAP:
        return _ENTITY_MAP[et]

    # Fallback
    return ("otros", et.lower())


def _resolve_estado(
    default_state: EvidenceState,
    entity: ExtractedEntity,
    notes_out: list[str],
) -> str:
    """Determina el estado del hecho candidato y añade notas si procede."""
    # ASUNCION_TEST global: todos los hechos salen como ASUNCION_TEST
    if default_state is EvidenceState.ASUNCION_TEST:
        notes_out.append(_NOTE_ASUNCION)
        return EvidenceState.ASUNCION_TEST.value

    # Confianza LOW: mantener DECLARADO pero añadir nota
    if entity.confidence == "LOW":
        notes_out.append(_NOTE_LOW_CONFIDENCE)

    return default_state.value


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def classify_entities(
    result: ExtractionResult,
    source_doc_id: str,
    source_doc_name: str,
    default_state: Union[EvidenceState, str] = EvidenceState.DECLARADO,
) -> "ClassificationResult":
    """Clasifica entidades de IN-02 en hechos candidatos estructurados.

    Args:
        result:          ExtractionResult de IN-02.
        source_doc_id:   Identificador documental (e.g. "DOC-001").
        source_doc_name: Nombre del documento (e.g. "Documento_Ambiental.docx").
        default_state:   Estado base para todos los hechos. Acepta EvidenceState
                         o string normalizable por EvidenceState.from_string().
                         Casi siempre DECLARADO (dato del promotor).

    Returns:
        ClassificationResult con hechos candidatos, avisos y conflictos.
    """
    # Normalizar default_state
    if isinstance(default_state, str):
        default_state = EvidenceState.from_string(default_state)

    fuentes = [source_doc_id]
    facts: list[CandidateFact] = []
    warnings: list[str] = list(result.warnings)

    for entity in result.entities:
        notes: list[str] = []
        estado_str = _resolve_estado(default_state, entity, notes)
        categoria, campo = _resolve_categoria_campo(entity)

        valor: object = entity.normalized_value if entity.normalized_value else entity.value

        facts.append(CandidateFact(
            id=None,
            categoria=categoria,
            campo=campo,
            valor=valor,
            estado=estado_str,
            fuentes=fuentes,
            entity_type=entity.entity_type,
            confidence=entity.confidence,
            context=entity.context,
            normalized_value=entity.normalized_value,
            notes=notes,
        ))

    conflicts = detect_simple_conflicts(facts)
    for c in conflicts:
        warnings.append(
            f"Conflicto en {c['categoria']}/{c['campo']}: "
            f"{len(c['valores'])} valores distintos detectados."
        )

    return ClassificationResult(facts=facts, warnings=warnings, conflicts=conflicts)


# ---------------------------------------------------------------------------
# Función de acceso desde DOCX
# ---------------------------------------------------------------------------

def classify_entities_from_docx(
    path: "str | Path",
    source_doc_id: str | None = None,
    default_state: Union[EvidenceState, str] = EvidenceState.DECLARADO,
) -> ClassificationResult:
    """Extrae y clasifica entidades de un .docx en un solo paso.

    Usa parse_docx() (IN-01) y extract_entities_from_docx() (IN-02) internamente.
    No escribe nada en disco.

    Args:
        path:          Ruta al archivo .docx.
        source_doc_id: ID documental. Si es None, usa "DOC-001".
        default_state: Estado base para todos los hechos.

    Returns:
        ClassificationResult con hechos candidatos.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError: si no es un DOCX válido.
    """
    from eia_agent.core.entity_extractor import extract_entities_from_docx

    path = Path(path)
    doc_id = source_doc_id or "DOC-001"
    doc_name = path.name

    extraction = extract_entities_from_docx(path)
    return classify_entities(extraction, doc_id, doc_name, default_state)


# ---------------------------------------------------------------------------
# Detección de conflictos
# ---------------------------------------------------------------------------

def detect_simple_conflicts(facts: list[CandidateFact]) -> list[dict]:
    """Detecta conflictos simples: mismo campo con varios valores distintos.

    No resuelve los conflictos. Solo los registra.

    Returns:
        Lista de dicts: {categoria, campo, valores: list[object], fact_count: int}
    """
    groups: dict[tuple[str, str], list[object]] = {}
    for f in facts:
        key = (f.categoria, f.campo)
        groups.setdefault(key, [])
        # Normalizar valor para comparación: convertir a str para hashability
        val_repr = str(f.valor)
        if val_repr not in [str(v) for v in groups[key]]:
            groups[key].append(f.valor)

    conflicts = []
    for (categoria, campo), valores in groups.items():
        if len(valores) > 1:
            conflicts.append({
                "categoria": categoria,
                "campo": campo,
                "valores": valores,
                "fact_count": sum(
                    1 for f in facts
                    if f.categoria == categoria and f.campo == campo
                ),
            })
    return conflicts
