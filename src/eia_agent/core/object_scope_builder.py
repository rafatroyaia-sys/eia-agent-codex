"""
object_scope_builder -- OB-01
Construye la ficha del objeto evaluado a partir de un ClassificationResult
(IN-03) y/o overrides explícitos del usuario.

No usa IA. No escribe automáticamente. No resuelve contradicciones.
No confirma administrativamente ningún dato.

Uso:
    from eia_agent.core.object_scope_builder import build_object_scope

    scope = build_object_scope(
        "expediente-EIA-2026-RECIMETAL-PARCELA",
        classification=classification_result,
        overrides={"modo": "GABINETE", "operaciones_excluidas": ["R1302"]},
    )
    print(scope.to_markdown())
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from eia_agent.core.evidence_classifier import ClassificationResult


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_MODOS_VALIDOS = frozenset({"GABINETE", "CAMPO", "NO_DECLARADO"})

_NO_DECLARADO = "NO DECLARADO"


# ---------------------------------------------------------------------------
# Dataclass ObjectScope
# ---------------------------------------------------------------------------

@dataclass
class ObjectScope:
    """Representación estructurada del objeto evaluado en un expediente EIA.

    Agrupa los campos mínimos requeridos por el gate 2: titular, RC,
    coordenadas, operaciones, modo de trabajo, AT activos y gaps.

    No confirma administrativamente ningún dato — todo proviene de
    documentos del promotor (DECLARADO) o de overrides explícitos.
    """
    expediente_id: str
    titular: str | None
    referencia_catastral: str | None
    coordenadas_wgs84: list[str]
    coordenadas_utm: list[str]
    operaciones_incluidas: list[str]
    operaciones_excluidas: list[str]
    modo: str                           # GABINETE | CAMPO | NO_DECLARADO
    superficie_m2: str | None
    capacidad: str | None
    at_activos: list[str]
    gaps: list[str]
    estado_gate2: str                   # APTO | PENDIENTE | BLOQUEADO
    fuentes: list[str]
    notes: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Constructor alternativo
    # ------------------------------------------------------------------

    @classmethod
    def from_classification(
        cls,
        result: ClassificationResult,
        expediente_id: str,
    ) -> "ObjectScope":
        """Construye un ObjectScope extrayendo datos de un ClassificationResult.

        Los campos que ClassificationResult no puede determinar (modo,
        operaciones_excluidas, at_activos, gaps) se inicializan a sus
        valores por defecto. El llamador puede complementarlos con overrides.
        """
        # Titular / promotor
        titular: str | None = None
        promotor_vals = result.values("nombre_promotor")
        if not promotor_vals:
            promotor_vals = result.values("titular")
        if promotor_vals:
            # Tomar el de mayor confianza (HIGH antes que MEDIUM/LOW)
            high = [f for f in result.by_field("nombre_promotor")
                    if f.confidence == "HIGH"]
            titular = (high[0].valor if high else str(promotor_vals[0])) or None
            if titular:
                titular = str(titular).strip() or None

        # Referencia catastral
        referencia_catastral: str | None = None
        rc_vals = result.values("referencia_catastral")
        if rc_vals:
            referencia_catastral = str(rc_vals[0]).strip() or None

        # Coordenadas — strip disambiguation prefix ("DEC "/"UTM ") before storing
        def _strip_coord_prefix(val: object, prefix: str) -> str:
            s = str(val)
            if s.upper().startswith(prefix.upper()):
                s = s[len(prefix):].strip()
            return s

        coordenadas_wgs84 = [
            _strip_coord_prefix(v, "DEC ")
            for v in result.values("coordenadas_wgs84")
        ]
        coordenadas_utm = [
            _strip_coord_prefix(v, "UTM ")
            for v in result.values("coordenadas_utm")
        ]

        # Operaciones incluidas
        operaciones_incluidas = [str(v) for v in result.values("operacion_residuos")]

        # Superficies — tomar la primera de cualquier subtipo
        superficie_m2: str | None = None
        for campo in ("superficie_parcela", "superficie_catastral",
                      "superficie_construida", "superficie_util",
                      "superficie_nave", "superficie_no_clasificada"):
            vals = result.values(campo)
            if vals:
                superficie_m2 = str(vals[0]).strip() or None
                break

        # Capacidad
        capacidad: str | None = None
        cap_vals = result.values("capacidad")
        if cap_vals:
            capacidad = str(cap_vals[0]).strip() or None

        # Fuentes documentales únicas
        fuentes: list[str] = []
        seen_fuentes: set[str] = set()
        for fact in result.facts:
            for f in fact.fuentes:
                if f not in seen_fuentes:
                    seen_fuentes.add(f)
                    fuentes.append(f)

        return cls(
            expediente_id=expediente_id,
            titular=titular,
            referencia_catastral=referencia_catastral,
            coordenadas_wgs84=coordenadas_wgs84,
            coordenadas_utm=coordenadas_utm,
            operaciones_incluidas=operaciones_incluidas,
            operaciones_excluidas=[],
            modo="NO_DECLARADO",
            superficie_m2=superficie_m2,
            capacidad=capacidad,
            at_activos=[],
            gaps=[],
            estado_gate2=_compute_estado_gate2(
                titular, referencia_catastral,
                coordenadas_wgs84, coordenadas_utm,
                operaciones_incluidas,
            ),
            fuentes=fuentes,
        )

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ObjectScope":
        """Reconstruye un ObjectScope desde un dict (e.g. cargado de JSON)."""
        required = (
            "expediente_id", "titular", "referencia_catastral",
            "coordenadas_wgs84", "coordenadas_utm",
            "operaciones_incluidas", "operaciones_excluidas",
            "modo", "superficie_m2", "capacidad",
            "at_activos", "gaps", "estado_gate2", "fuentes",
        )
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"Campos faltantes en dict: {missing}")
        return cls(
            expediente_id=data["expediente_id"],
            titular=data["titular"],
            referencia_catastral=data["referencia_catastral"],
            coordenadas_wgs84=list(data["coordenadas_wgs84"]),
            coordenadas_utm=list(data["coordenadas_utm"]),
            operaciones_incluidas=list(data["operaciones_incluidas"]),
            operaciones_excluidas=list(data["operaciones_excluidas"]),
            modo=data["modo"],
            superficie_m2=data["superficie_m2"],
            capacidad=data["capacidad"],
            at_activos=list(data["at_activos"]),
            gaps=list(data["gaps"]),
            estado_gate2=data["estado_gate2"],
            fuentes=list(data["fuentes"]),
            notes=list(data.get("notes", [])),
        )

    # ------------------------------------------------------------------
    # Generación de markdown
    # ------------------------------------------------------------------

    def to_markdown(self) -> str:
        """Genera el texto Markdown de la ficha del objeto evaluado.

        Todas las 10 secciones están presentes siempre.
        Los campos ausentes se muestran como 'NO DECLARADO'.
        """
        lines: list[str] = [
            f"# Ficha del Objeto Evaluado — {self.expediente_id}",
            "",
        ]

        # 1. Identificación
        lines += [
            "## 1. Identificación del promotor/titular",
            "",
            f"- **Titular/Promotor:** {self.titular or _NO_DECLARADO}",
            "",
        ]

        # 2. Emplazamiento
        wgs84_str = (", ".join(self.coordenadas_wgs84)
                     if self.coordenadas_wgs84 else _NO_DECLARADO)
        utm_str = (", ".join(self.coordenadas_utm)
                   if self.coordenadas_utm else _NO_DECLARADO)
        lines += [
            "## 2. Emplazamiento",
            "",
            f"- **Referencia catastral:** {self.referencia_catastral or _NO_DECLARADO}",
            f"- **Coordenadas WGS84:** {wgs84_str}",
            f"- **Coordenadas UTM:** {utm_str}",
            "",
        ]

        # 3. Operaciones incluidas
        if self.operaciones_incluidas:
            ops_lines = [""]
            for op in self.operaciones_incluidas:
                ops_lines.append(f"  - {op}")
            ops_str = "\n".join(ops_lines)
        else:
            ops_str = f" {_NO_DECLARADO}"
        lines += [
            "## 3. Operaciones autorizadas/solicitadas",
            "",
            f"- **Operaciones incluidas:**{ops_str}",
            "",
        ]

        # 4. Operaciones excluidas
        if self.operaciones_excluidas:
            excl_lines = [""]
            for op in self.operaciones_excluidas:
                excl_lines.append(f"  - {op}")
            excl_str = "\n".join(excl_lines)
        else:
            excl_str = f" {_NO_DECLARADO}"
        lines += [
            "## 4. Operaciones excluidas del objeto evaluado",
            "",
            f"- **Operaciones excluidas:**{excl_str}",
            "",
        ]

        # 5. Superficies y capacidades
        lines += [
            "## 5. Superficies y capacidades",
            "",
            f"- **Superficie:** {self.superficie_m2 or _NO_DECLARADO}",
            f"- **Capacidad:** {self.capacidad or _NO_DECLARADO}",
            "",
        ]

        # 6. Modo de trabajo
        lines += [
            "## 6. Modo de trabajo",
            "",
            f"- **Modo declarado:** {self.modo}",
            "",
        ]

        # 7. AT activos
        if self.at_activos:
            at_lines = [""]
            for at in self.at_activos:
                at_lines.append(f"  - ⚠️ {at}")
            at_str = "\n".join(at_lines)
        else:
            at_str = f" {_NO_DECLARADO}"
        lines += [
            "## 7. Asunciones de test activas",
            "",
            f"- **AT activos:**{at_str}",
            "",
        ]

        # 8. Gaps
        if self.gaps:
            gap_lines = [""]
            for g in self.gaps:
                gap_lines.append(f"  - 🔴 {g}")
            gap_str = "\n".join(gap_lines)
        else:
            gap_str = f" {_NO_DECLARADO}"
        lines += [
            "## 8. Gaps identificados",
            "",
            f"- **Gaps:**{gap_str}",
            "",
        ]

        # 9. Estado gate 2
        estado_emoji = {
            "APTO": "✅",
            "PENDIENTE": "⚠️",
            "BLOQUEADO": "🔴",
        }.get(self.estado_gate2, "")
        lines += [
            "## 9. Estado del gate 2",
            "",
            f"- **Estado:** {estado_emoji} {self.estado_gate2}",
            "",
        ]
        if self.notes:
            lines.append("- **Notas:**")
            for n in self.notes:
                lines.append(f"  - {n}")
            lines.append("")

        # 10. Fuentes
        if self.fuentes:
            fuentes_str = ", ".join(self.fuentes)
        else:
            fuentes_str = _NO_DECLARADO
        lines += [
            "## 10. Fuentes documentales",
            "",
            f"- **Fuentes:** {fuentes_str}",
            "",
        ]

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Lógica de estado gate 2
# ---------------------------------------------------------------------------

def _compute_estado_gate2(
    titular: str | None,
    referencia_catastral: str | None,
    coordenadas_wgs84: list[str],
    coordenadas_utm: list[str],
    operaciones_incluidas: list[str],
) -> str:
    tiene_coords = bool(coordenadas_wgs84 or coordenadas_utm)

    # BLOQUEADO: sin titular, sin RC y sin coordenadas
    if not titular and not referencia_catastral and not tiene_coords:
        return "BLOQUEADO"

    # APTO: todos los campos críticos presentes
    if titular and referencia_catastral and tiene_coords and operaciones_incluidas:
        return "APTO"

    # PENDIENTE: datos parciales
    return "PENDIENTE"


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def build_object_scope(
    expediente_id: str,
    classification: Optional[ClassificationResult] = None,
    overrides: Optional[dict] = None,
) -> ObjectScope:
    """Construye un ObjectScope a partir de una clasificación y/o overrides.

    Args:
        expediente_id:  ID del expediente (e.g. "expediente-EIA-2026-...").
        classification: ClassificationResult de IN-03. Puede ser None si
                        se proporcionan todos los datos vía overrides.
        overrides:      Dict con campos a sobreescribir o añadir.
                        Claves admitidas: titular, referencia_catastral,
                        coordenadas_wgs84, coordenadas_utm,
                        operaciones_incluidas, operaciones_excluidas,
                        modo, superficie_m2, capacidad,
                        at_activos, gaps, fuentes, notes.

    Returns:
        ObjectScope con estado_gate2 calculado.
    """
    overrides = overrides or {}

    if classification is not None:
        scope = ObjectScope.from_classification(classification, expediente_id)
    else:
        scope = ObjectScope(
            expediente_id=expediente_id,
            titular=None,
            referencia_catastral=None,
            coordenadas_wgs84=[],
            coordenadas_utm=[],
            operaciones_incluidas=[],
            operaciones_excluidas=[],
            modo="NO_DECLARADO",
            superficie_m2=None,
            capacidad=None,
            at_activos=[],
            gaps=[],
            estado_gate2="BLOQUEADO",
            fuentes=[],
        )

    # Aplicar overrides campo a campo
    scalar_fields = {
        "titular", "referencia_catastral", "modo",
        "superficie_m2", "capacidad",
    }
    list_fields = {
        "coordenadas_wgs84", "coordenadas_utm",
        "operaciones_incluidas", "operaciones_excluidas",
        "at_activos", "gaps", "fuentes", "notes",
    }

    for key, value in overrides.items():
        if key in scalar_fields:
            setattr(scope, key, value)
        elif key in list_fields:
            setattr(scope, key, list(value))

    # Validar modo
    if scope.modo not in _MODOS_VALIDOS:
        scope.notes.append(
            f"Modo '{scope.modo}' no reconocido; se usa NO_DECLARADO."
        )
        scope.modo = "NO_DECLARADO"

    # Recalcular estado_gate2 con datos finales
    scope.estado_gate2 = _compute_estado_gate2(
        scope.titular,
        scope.referencia_catastral,
        scope.coordenadas_wgs84,
        scope.coordenadas_utm,
        scope.operaciones_incluidas,
    )

    return scope


# ---------------------------------------------------------------------------
# Escritura y carga
# ---------------------------------------------------------------------------

def write_object_scope_markdown(
    scope: ObjectScope,
    output_path: "str | Path",
) -> Path:
    """Escribe la ficha como Markdown. No se llama automáticamente."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(scope.to_markdown(), encoding="utf-8")
    return output_path


def write_object_scope_json(
    scope: ObjectScope,
    output_path: "str | Path",
) -> Path:
    """Escribe el ObjectScope como JSON UTF-8 indentado. No automático."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(scope.to_dict(), f, ensure_ascii=False, indent=2)
    return output_path


def load_object_scope_json(path: "str | Path") -> ObjectScope:
    """Carga un ObjectScope desde JSON previamente generado.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError: si el JSON no es válido o la estructura es incorrecta.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Ficha no encontrada: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en {path}: {exc}") from exc
    return ObjectScope.from_dict(data)
