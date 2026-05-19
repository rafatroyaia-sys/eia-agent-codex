"""
phase3_pipeline -- TN-05
Pipeline programático de Fase 3: triaje normativo básico.

Toma los datos de Fase 1 (candidate_facts) y Fase 2 (object_scope),
detecta normativa potencialmente aplicable mediante reglas Python puras
y produce una nota de encuadre legal preliminar.

No usa IA. No consulta el BOE online. No hace web scraping.
No afirma verificación jurídica. No declara aptitud administrativa.
No escribe automáticamente (requiere write_outputs=True).
No inicia Fase 4.

La normativa con estado REFERENCIADA aplica según las reglas del triaje.
NO significa que esté verificada contra el BOE en la fecha de consulta.
PENDIENTE_VERIFICACION requiere comprobación manual antes de usar.

Uso:
    from eia_agent.core.phase3_pipeline import run_phase3

    result = run_phase3("expediente-EIA-2026-RECIMETAL-PARCELA")
    print(result.summary())

    result = run_phase3(
        "expediente-EIA-2026-RECIMETAL-PARCELA",
        write_outputs=True,
    )
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constantes de detección
# ---------------------------------------------------------------------------

_RESIDUOS_CAMPOS = frozenset({"codigo_ler", "operacion_residuos"})
_RESIDUOS_ENTITY_TYPES = frozenset({"LER", "OPERACION", "OPERACION_RESIDUOS"})
_RESIDUOS_KEYWORDS = frozenset({
    "residuo", "gestión de residuos", "gestion de residuos",
    " r12", " r13", " d1", " d15",
    "valorización", "valorizacion", "almacenamiento de residuos",
    "ler ", "código ler", "codigo ler",
})

_RUIDO_CAMPOS = frozenset({"equipo", "potencia"})
_RUIDO_ENTITY_TYPES = frozenset({"EQUIPO", "POTENCIA"})
_RUIDO_KEYWORDS = frozenset({
    "maquinaria", "trituradora", "trituración", "trituracion",
    "compresor", "compresora", "prensa", "cizalla", "molino",
    "motor", "equipo mecánico", "equipo mecanico",
    "vibración", "vibracion", "ruido", "emisión sonora",
    "nivel sonoro", "nivel de ruido", "impacto acústico", "acustico",
})

_NATURA_KEYWORDS = frozenset({
    "lic", "zec", "zepa", "red natura", "natura 2000", "natura2000",
    "hábitat", "habitat", "especie protegida", "flora protegida",
    "fauna protegida", "afección apreciable", "afeccion apreciable",
    "eiha", "evaluación de impacto en hábitats",
    "evaluacion de impacto en habitats",
    "lugar de importancia comunitaria",
    "zona especial de conservación", "zona especial de conservacion",
    "zona de especial protección", "zona de especial proteccion",
})

_PATRIMONIO_KEYWORDS = frozenset({
    "patrimonio", "arqueología", "arqueologia", "arqueológico",
    "arqueologico", "bienes culturales", "bien de interés cultural",
    "bien de interes cultural", "bic", "catálogo de protección",
    "catalogo de proteccion", "igpc", "yacimiento", "excavación",
    "excavacion", "carta arqueológica", "carta arqueologica",
    "protección del patrimonio", "proteccion del patrimonio",
})

_CANARIAS_KEYWORDS = frozenset({
    "canarias", "canario", "canaria", "gran canaria", "grancanaria",
    "tenerife", "lanzarote", "fuerteventura", "la gomera", "el hierro",
    "la palma", "la graciosa", "cabildo", "grafcan", "riesgomap",
    "caarup", "regcan", "idec", "idecanarias",
})

_URBANISMO_CAMPOS = frozenset({"referencia_catastral"})
_URBANISMO_KEYWORDS = frozenset({
    "pgou", "planeamiento", "uso catastral", "uso del suelo",
    "suelo urbano", "suelo industrial", "calificación urbanística",
    "calificacion urbanistica", "clasificación urbanística",
    "clasificacion urbanistica", "compatibilidad urbanística",
    "compatibilidad urbanistica", "ordenanza municipal",
    "plan general", "plan parcial", "normativa urbanística",
    "normativa urbanistica", "suelo no urbanizable",
})

_ALTA_CAPACIDAD_KEYWORDS = frozenset({
    "fraccionamiento", "conjunto operativo", "umbral de",
    "anexo i", "evaluación ordinaria", "evaluacion ordinaria",
    "alta capacidad", "superación de umbral", "superacion de umbral",
})

# Coordenadas aproximadas de Canarias
_CANARIAS_LAT_MIN, _CANARIAS_LAT_MAX = 27.0, 30.0
_CANARIAS_LON_MIN, _CANARIAS_LON_MAX = -19.0, -13.0


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class NormativeItem:
    """Norma detectada por el triaje normativo de Fase 3.

    Estado:
    - REFERENCIADA: aplica según reglas del triaje. Verificar vigencia online.
    - PENDIENTE_VERIFICACION: mención detectada; requiere comprobación manual.
    - VERIFICADA_ONLINE: verificada contra BOE/BOC en fecha de consulta (TN-01, futuro).
    """
    id: str
    titulo: str
    ambito: str        # estatal / autonomico / local / europeo / desconocido
    materia: str       # evaluacion_ambiental / residuos / ruido / agua /
                       # patrimonio / natura2000 / clima / urbanismo /
                       # seguridad / otro
    referencia: str | None
    estado: str        # REFERENCIADA / PENDIENTE_VERIFICACION / VERIFICADA_ONLINE
    razon_aplicabilidad: str
    fuente_deteccion: str
    notas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "titulo": self.titulo,
            "ambito": self.ambito,
            "materia": self.materia,
            "referencia": self.referencia,
            "estado": self.estado,
            "razon_aplicabilidad": self.razon_aplicabilidad,
            "fuente_deteccion": self.fuente_deteccion,
            "notas": list(self.notas),
        }


@dataclass
class Phase3Result:
    """Resultado completo del pipeline de Fase 3.

    Contiene normativa detectada, procedimiento EIA preliminar,
    cautelas y avisos. No confirma aptitud administrativa.
    """
    expediente_id: str
    normativa: list[NormativeItem]
    procedimiento_eia: str        # SIMPLIFICADA / ORDINARIA_POSIBLE / NO_DETERMINADO
    razones_procedimiento: list[str]
    cautelas: list[str]
    warnings: list[str]
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Fase 3 — {self.expediente_id}",
            f"  Procedimiento EIA      : {self.procedimiento_eia}",
            f"  Normas detectadas      : {len(self.normativa)}",
        ]
        by_materia: dict[str, int] = {}
        for n in self.normativa:
            by_materia[n.materia] = by_materia.get(n.materia, 0) + 1
        for materia, count in sorted(by_materia.items()):
            lines.append(f"    {materia}: {count}")
        if self.cautelas:
            lines.append(f"  Cautelas               : {len(self.cautelas)}")
        if self.warnings:
            lines.append(f"  Avisos                 : {len(self.warnings)}")
            for w in self.warnings[:3]:
                lines.append(f"    - {w}")
            if len(self.warnings) > 3:
                lines.append(f"    ... y {len(self.warnings) - 3} aviso(s) más")
        for n in self.notes:
            lines.append(f"  Nota: {n}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "normativa": [n.to_dict() for n in self.normativa],
            "procedimiento_eia": self.procedimiento_eia,
            "razones_procedimiento": list(self.razones_procedimiento),
            "cautelas": list(self.cautelas),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# Helpers de detección
# ---------------------------------------------------------------------------

def _has_any_keyword(text: str, keywords: frozenset) -> tuple[bool, str]:
    """Busca cualquier keyword en texto. Case-insensitive. Devuelve (found, keyword)."""
    t = text.lower()
    for kw in keywords:
        if kw in t:
            return True, kw
    return False, ""


def _build_text_corpus(candidate_facts: list[dict], object_scope: dict) -> str:
    """Construye corpus de texto de todos los campos relevantes para detección."""
    parts: list[str] = []
    for fact in candidate_facts:
        for fld in ("valor", "context", "normalized_value"):
            val = fact.get(fld)
            if val:
                parts.append(str(val))
        for note in fact.get("notes", []):
            parts.append(str(note))
    for fld in ("titular", "modo", "capacidad", "superficie_m2"):
        val = object_scope.get(fld)
        if val:
            parts.append(str(val))
    for ops in object_scope.get("operaciones_incluidas", []):
        parts.append(str(ops))
    for ops in object_scope.get("operaciones_excluidas", []):
        parts.append(str(ops))
    for gap in object_scope.get("gaps", []):
        parts.append(str(gap))
    for at in object_scope.get("at_activos", []):
        parts.append(str(at))
    return " ".join(parts)


def _detect_residuos(
    candidate_facts: list[dict],
    text_corpus: str,
) -> tuple[bool, str]:
    """Detecta operaciones o códigos de residuos."""
    for fact in candidate_facts:
        campo = fact.get("campo", "")
        entity_type = fact.get("entity_type", "")
        if campo in _RESIDUOS_CAMPOS:
            return True, f"campo:{campo}"
        if entity_type in _RESIDUOS_ENTITY_TYPES:
            return True, f"entity_type:{entity_type}"
    found, kw = _has_any_keyword(text_corpus, _RESIDUOS_KEYWORDS)
    if found:
        return True, f"texto:{kw}"
    return False, ""


def _has_r12_r13_operations(
    candidate_facts: list[dict],
    object_scope: dict,
) -> bool:
    """Detecta específicamente operaciones R12 o R13."""
    for fact in candidate_facts:
        if fact.get("campo") == "operacion_residuos":
            val = str(fact.get("valor", "")).upper()
            if val.startswith("R12") or val.startswith("R13"):
                return True
    for op in object_scope.get("operaciones_incluidas", []):
        op_upper = str(op).upper()
        if op_upper.startswith("R12") or op_upper.startswith("R13"):
            return True
    return False


def _detect_ruido(
    candidate_facts: list[dict],
    text_corpus: str,
) -> tuple[bool, str]:
    """Detecta maquinaria o equipos que generan ruido."""
    for fact in candidate_facts:
        campo = fact.get("campo", "")
        entity_type = fact.get("entity_type", "")
        if campo in _RUIDO_CAMPOS:
            return True, f"campo:{campo}"
        if entity_type in _RUIDO_ENTITY_TYPES:
            return True, f"entity_type:{entity_type}"
    found, kw = _has_any_keyword(text_corpus, _RUIDO_KEYWORDS)
    if found:
        return True, f"texto:{kw}"
    return False, ""


def _detect_natura(text_corpus: str) -> tuple[bool, str]:
    """Detecta menciones a Red Natura 2000 o espacios protegidos."""
    found, kw = _has_any_keyword(text_corpus, _NATURA_KEYWORDS)
    if found:
        return True, f"texto:{kw}"
    return False, ""


def _detect_patrimonio(text_corpus: str) -> tuple[bool, str]:
    """Detecta menciones a patrimonio cultural o arqueológico."""
    found, kw = _has_any_keyword(text_corpus, _PATRIMONIO_KEYWORDS)
    if found:
        return True, f"texto:{kw}"
    return False, ""


def _detect_canarias(
    object_scope: dict,
    text_corpus: str,
) -> tuple[bool, str]:
    """Detecta si el proyecto está en Canarias por coords o keywords."""
    for coord_str in object_scope.get("coordenadas_wgs84", []):
        parts = coord_str.replace(" ", "").split(",")
        if len(parts) >= 2:
            try:
                lat = float(parts[0])
                lon = float(parts[1])
                if (_CANARIAS_LAT_MIN <= lat <= _CANARIAS_LAT_MAX
                        and _CANARIAS_LON_MIN <= lon <= _CANARIAS_LON_MAX):
                    return True, f"coordenadas_wgs84:{coord_str}"
            except (ValueError, IndexError):
                pass
    found, kw = _has_any_keyword(text_corpus, _CANARIAS_KEYWORDS)
    if found:
        return True, f"texto:{kw}"
    return False, ""


def _detect_urbanismo(
    candidate_facts: list[dict],
    object_scope: dict,
    text_corpus: str,
) -> tuple[bool, str]:
    """Detecta indicios de cuestiones urbanísticas o catastrales."""
    if object_scope.get("referencia_catastral"):
        return True, "object_scope:referencia_catastral"
    for fact in candidate_facts:
        if fact.get("campo") in _URBANISMO_CAMPOS:
            return True, f"campo:{fact['campo']}"
    found, kw = _has_any_keyword(text_corpus, _URBANISMO_KEYWORDS)
    if found:
        return True, f"texto:{kw}"
    return False, ""


def _detect_alta_capacidad(
    object_scope: dict,
    text_corpus: str,
) -> tuple[bool, str]:
    """Detecta indicios de superación de umbral o evaluación ordinaria."""
    found, kw = _has_any_keyword(text_corpus, _ALTA_CAPACIDAD_KEYWORDS)
    if found:
        return True, f"texto:{kw}"
    # Capacidad numérica alta (>50000 t/año como heurística conservadora)
    capacidad = object_scope.get("capacidad", "")
    if capacidad:
        nums = re.findall(r"[\d]+", str(capacidad).replace(".", "").replace(",", ""))
        for n_str in nums:
            try:
                if int(n_str) > 50000:
                    return True, f"capacidad_elevada:{capacidad}"
            except ValueError:
                pass
    return False, ""


# ---------------------------------------------------------------------------
# Generación de normativa
# ---------------------------------------------------------------------------

def _build_normativa(
    has_residuos: bool,
    residuos_source: str,
    has_ruido: bool,
    ruido_source: str,
    has_natura: bool,
    natura_source: str,
    has_patrimonio: bool,
    patrimonio_source: str,
    has_canarias: bool,
    canarias_source: str,
    has_urbanismo: bool,
    urbanismo_source: str,
) -> list[NormativeItem]:
    """Construye la lista de NormativeItem según los flags de detección."""
    items: list[NormativeItem] = []

    # A. Ley 21/2013 — SIEMPRE
    items.append(NormativeItem(
        id="TN-A001",
        titulo="Ley 21/2013, de 9 de diciembre, de evaluación ambiental",
        ambito="estatal",
        materia="evaluacion_ambiental",
        referencia="BOE-A-2013-12913",
        estado="REFERENCIADA",
        razon_aplicabilidad=(
            "Marco legal base para todo Documento Ambiental de EIA simplificada "
            "(arts. 7, 16, 45, 46, 47 y Anexos II-III)."
        ),
        fuente_deteccion="regla_base",
        notas=[
            "Verificar vigencia y modificaciones recientes (RD 445/2023, posibles DL autonómicos).",
            "Confirmar encuadre en Anexo II (simplificada) o Anexo I (ordinaria).",
        ],
    ))

    # B. RD 445/2023 — SIEMPRE
    items.append(NormativeItem(
        id="TN-B001",
        titulo="Real Decreto 445/2023, de 13 de junio, por el que se modifican los Anexos I, II y III de la Ley 21/2013",
        ambito="estatal",
        materia="evaluacion_ambiental",
        referencia="BOE-A-2023-13785",
        estado="REFERENCIADA",
        razon_aplicabilidad=(
            "Modifica los umbrales y criterios de los Anexos I, II y III de Ley 21/2013; "
            "determina el encuadre procedimental aplicable."
        ),
        fuente_deteccion="regla_base",
        notas=["Revisar específicamente el grupo y epígrafe aplicable al tipo de proyecto."],
    ))

    # C. Ley 7/2022 — si residuos detectados
    if has_residuos:
        items.append(NormativeItem(
            id="TN-C001",
            titulo="Ley 7/2022, de 8 de abril, de residuos y suelos contaminados para una economía circular",
            ambito="estatal",
            materia="residuos",
            referencia="BOE-A-2022-5809",
            estado="REFERENCIADA",
            razon_aplicabilidad=(
                f"Detectadas operaciones de gestión de residuos "
                f"(LER, operaciones R/D) en el expediente [{residuos_source}]."
            ),
            fuente_deteccion=residuos_source,
            notas=[
                "Verificar clasificación LER y operaciones autorizadas en resolución administrativa.",
                "Comprobar inscripción en el Registro de Producción y Gestión de Residuos.",
            ],
        ))

    # D. Ley 37/2003 + RD 1367/2007 — si maquinaria / ruido detectado
    if has_ruido:
        items.append(NormativeItem(
            id="TN-D001",
            titulo="Ley 37/2003, de 17 de noviembre, del Ruido",
            ambito="estatal",
            materia="ruido",
            referencia="BOE-A-2003-20976",
            estado="REFERENCIADA",
            razon_aplicabilidad=(
                f"Detectada maquinaria, equipos o actividades con potencial impacto acústico "
                f"[{ruido_source}]."
            ),
            fuente_deteccion=ruido_source,
            notas=["Verificar umbrales acústicos y mapa de ruido del municipio afectado."],
        ))
        items.append(NormativeItem(
            id="TN-D002",
            titulo="Real Decreto 1367/2007, de 19 de octubre, sobre zonificación acústica, objetivos de calidad y emisiones acústicas",
            ambito="estatal",
            materia="ruido",
            referencia="BOE-A-2007-18397",
            estado="REFERENCIADA",
            razon_aplicabilidad=(
                "Complemento al RD 1513/2005 y Ley 37/2003; "
                "establece valores límite de emisión e inmisión acústica."
            ),
            fuente_deteccion=ruido_source,
            notas=[],
        ))

    # E. Ley 42/2007 — si Natura 2000 detectado
    if has_natura:
        items.append(NormativeItem(
            id="TN-E001",
            titulo="Ley 42/2007, de 13 de diciembre, del Patrimonio Natural y de la Biodiversidad",
            ambito="estatal",
            materia="natura2000",
            referencia="BOE-A-2007-21490",
            estado="REFERENCIADA",
            razon_aplicabilidad=(
                f"Detectada mención a espacios Red Natura 2000, hábitats o "
                f"especies protegidas [{natura_source}]. "
                "Verificar posible afección apreciable y necesidad de EIHA."
            ),
            fuente_deteccion=natura_source,
            notas=[
                "Si procede afección apreciable, realizar Evaluación de Impacto en Hábitats (EIHA).",
                "No usar 'afección significativa' sin EIHA previa.",
            ],
        ))

    # F. Patrimonio cultural — si detectado
    if has_patrimonio:
        items.append(NormativeItem(
            id="TN-F001",
            titulo="Ley 16/1985, de 25 de junio, del Patrimonio Histórico Español",
            ambito="estatal",
            materia="patrimonio",
            referencia="BOE-A-1985-12534",
            estado="PENDIENTE_VERIFICACION",
            razon_aplicabilidad=(
                f"Detectada mención a patrimonio cultural o arqueológico "
                f"[{patrimonio_source}]. Requiere comprobación de afección."
            ),
            fuente_deteccion=patrimonio_source,
            notas=[
                "Verificar si la parcela está en zona de interés arqueológico o BIC.",
                "Puede requerirse informe previo del órgano de patrimonio.",
            ],
        ))

    # G. Canarias — si detectado
    if has_canarias:
        items.append(NormativeItem(
            id="TN-G001",
            titulo="Ley 4/2017, de 13 de julio, del Suelo y de los Espacios Naturales Protegidos de Canarias",
            ambito="autonomico",
            materia="urbanismo",
            referencia=None,
            estado="REFERENCIADA",
            razon_aplicabilidad=(
                f"Proyecto ubicado en Canarias [{canarias_source}]. "
                "Marco urbanístico y ambiental autonómico de aplicación."
            ),
            fuente_deteccion=canarias_source,
            notas=[
                "Verificar modificaciones recientes (DL 6/2025 que modifica la Ley 4/2017).",
                "El órgano ambiental competente es el CAARUP (Comisión de Afección Ambiental).",
            ],
        ))
        items.append(NormativeItem(
            id="TN-G002",
            titulo="Ley 6/2022, de 27 de diciembre, de cambio climático y transición energética de Canarias",
            ambito="autonomico",
            materia="clima",
            referencia=None,
            estado="REFERENCIADA",
            razon_aplicabilidad=(
                "Proyecto ubicado en Canarias. "
                "Marco climático autonómico; verificar integración de criterios de resiliencia."
            ),
            fuente_deteccion=canarias_source,
            notas=[
                "Verificar modificaciones: DL 5/2024 y DL 1/2026.",
            ],
        ))

    # H. Urbanismo — si referencia catastral u otros indicios
    if has_urbanismo:
        items.append(NormativeItem(
            id="TN-H001",
            titulo="Normativa urbanística municipal aplicable (PGOU/PIOT/PIOF o equivalente)",
            ambito="local",
            materia="urbanismo",
            referencia=None,
            estado="PENDIENTE_VERIFICACION",
            razon_aplicabilidad=(
                f"Detectada referencia catastral o indicios de cuestiones urbanísticas "
                f"[{urbanismo_source}]. Verificar compatibilidad con planeamiento vigente."
            ),
            fuente_deteccion=urbanismo_source,
            notas=[
                "Identificar el instrumento de planeamiento vigente en el municipio.",
                "Verificar clasificación y calificación del suelo en el planeamiento.",
                "Comprobar licencias urbanísticas preexistentes.",
            ],
        ))

    return items


# ---------------------------------------------------------------------------
# Determinación de procedimiento
# ---------------------------------------------------------------------------

def _determine_procedimiento(
    has_residuos: bool,
    has_alta_capacidad: bool,
    alta_capacidad_source: str,
    candidate_facts: list[dict],
    object_scope: dict,
) -> tuple[str, list[str]]:
    """Determina el procedimiento EIA preliminar."""
    razones: list[str] = []

    # ORDINARIA_POSIBLE si hay indicios de fraccionamiento o umbral alto
    if has_alta_capacidad:
        razones.append(
            f"Detectados indicios de posible superación de umbral Anexo I "
            f"o evaluación ordinaria [{alta_capacidad_source}]."
        )
        razones.append(
            "Requiere verificación contra RD 445/2023 antes de determinar procedimiento definitivo."
        )
        return "ORDINARIA_POSIBLE", razones

    # SIMPLIFICADA si operaciones R12/R13 y no hay indicios de Anexo I
    if has_residuos and _has_r12_r13_operations(candidate_facts, object_scope):
        ops = object_scope.get("operaciones_incluidas", [])
        ops_str = ", ".join(ops) if ops else "detectadas en documentación"
        razones.append(
            f"Operaciones R12/R13 detectadas ({ops_str}): "
            "probable encuadre en Anexo II Ley 21/2013 (evaluación simplificada)."
        )
        razones.append(
            "No se detectan indicios claros de superación de umbral Anexo I. "
            "Verificar contra RD 445/2023."
        )
        return "SIMPLIFICADA", razones

    # Residuos genéricos sin R12/R13 explícitos → SIMPLIFICADA provisional
    if has_residuos:
        razones.append(
            "Detectadas operaciones o materiales de residuos sin codificación R12/R13 explícita. "
            "Probable encuadre en Anexo II, pendiente verificación de operaciones exactas."
        )
        return "SIMPLIFICADA", razones

    # Sin datos suficientes
    razones.append(
        "Datos insuficientes para determinar el procedimiento de evaluación ambiental. "
        "Revisar candidate_facts y object_scope."
    )
    return "NO_DETERMINADO", razones


# ---------------------------------------------------------------------------
# Cautelas
# ---------------------------------------------------------------------------

def _build_cautelas(
    object_scope: dict,
    has_natura: bool,
    has_canarias: bool,
    procedimiento: str,
) -> list[str]:
    """Genera cautelas operativas basadas en el scope y el triaje."""
    cautelas: list[str] = []

    cautelas.append(
        "[CAUTELA-TN-01] Las normas con estado REFERENCIADA deben verificarse contra "
        "el BOE/BOC en la fecha de presentación. No usar normativa de memoria."
    )
    cautelas.append(
        "[CAUTELA-TN-02] Este triaje es automático y no sustituye la revisión jurídica "
        "completa por técnico competente."
    )

    if object_scope.get("modo", "NO_DECLARADO") == "GABINETE":
        cautelas.append(
            "[CAUTELA-TN-03] Modo GABINETE activo: los datos de inventario ambiental "
            "provienen solo de fuentes documentales. Verificar si algún factor requiere "
            "prospección de campo antes de redactar el DA."
        )

    if object_scope.get("at_activos"):
        cautelas.append(
            "[CAUTELA-TN-04] Hay asunciones de test activas en el ObjectScope. "
            "El expediente no es apto para tramitación administrativa real hasta "
            "que se sustituyan por datos confirmados."
        )

    if has_natura:
        cautelas.append(
            "[CAUTELA-TN-05] Detectada mención a Red Natura 2000 o espacios protegidos. "
            "No usar 'afección significativa' sin EIHA previa. "
            "Usar 'afección apreciable' mientras no se realice evaluación específica."
        )

    if has_canarias:
        cautelas.append(
            "[CAUTELA-TN-06] Expediente en Canarias: el órgano ambiental competente "
            "para EIA simplificada es el CAARUP. Verificar con la Consejería competente."
        )

    if procedimiento == "ORDINARIA_POSIBLE":
        cautelas.append(
            "[CAUTELA-TN-07] Procedimiento posiblemente ordinario: no iniciar redacción "
            "del DA hasta confirmar el encuadre procedimental definitivo."
        )

    return cautelas


# ---------------------------------------------------------------------------
# Escritura opcional
# ---------------------------------------------------------------------------

def _build_nota_encuadre_legal_md(result: Phase3Result) -> str:
    """Genera la nota de encuadre legal en Markdown."""
    hoy = date.today().isoformat()
    lines = [
        "# Nota de Encuadre Legal — Triaje Normativo Preliminar",
        "",
        f"**Expediente**: {result.expediente_id}",
        f"**Fecha de triaje**: {hoy}",
        "",
        "> ⚠️ **TRIAJE AUTOMÁTICO PRELIMINAR.** No sustituye revisión jurídica completa.",
        "> Las normas con estado REFERENCIADA deben verificarse contra el BOE/BOC",
        "> antes de la presentación administrativa.",
        "",
        "---",
        "",
        "## 1. Procedimiento EIA preliminar",
        "",
        f"**{result.procedimiento_eia}**",
        "",
    ]
    if result.razones_procedimiento:
        for r in result.razones_procedimiento:
            lines.append(f"- {r}")
    lines.append("")
    lines += [
        "---",
        "",
        "## 2. Normativa aplicable detectada",
        "",
        "| ID | Norma | Ámbito | Materia | Estado |",
        "|----|-------|--------|---------|--------|",
    ]
    for n in result.normativa:
        titulo_short = n.titulo[:70] + "..." if len(n.titulo) > 70 else n.titulo
        lines.append(
            f"| {n.id} | {titulo_short} | {n.ambito} | {n.materia} | {n.estado} |"
        )
    lines.append("")
    lines += ["### Detalle por norma", ""]
    for n in result.normativa:
        lines += [
            f"#### {n.id} — {n.titulo}",
            "",
            f"- **Ámbito**: {n.ambito}",
            f"- **Materia**: {n.materia}",
            f"- **Referencia**: {n.referencia or 'No disponible'}",
            f"- **Estado**: {n.estado}",
            f"- **Razón de aplicabilidad**: {n.razon_aplicabilidad}",
        ]
        if n.notas:
            lines.append("- **Notas**:")
            for nota in n.notas:
                lines.append(f"  - {nota}")
        lines.append("")
    lines += [
        "---",
        "",
        "## 3. Cautelas activas",
        "",
    ]
    for c in result.cautelas:
        lines.append(f"- {c}")
    lines.append("")
    if result.warnings:
        lines += ["---", "", "## 4. Avisos del pipeline", ""]
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")
    return "\n".join(lines)


def _write_phase3_outputs(result: Phase3Result, output_dir: Path) -> tuple[Path, Path]:
    """Escribe phase3_result.json y nota_encuadre_legal.md en output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "phase3_result.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2, default=str)

    md_path = output_dir / "nota_encuadre_legal.md"
    md_path.write_text(_build_nota_encuadre_legal_md(result), encoding="utf-8")

    return json_path, md_path


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def run_phase3(
    expediente_path: "str | Path",
    phase1_result_path: "str | Path | None" = None,
    phase2_result_path: "str | Path | None" = None,
    write_outputs: bool = False,
    output_dir: str = "control_interno",
) -> Phase3Result:
    """Ejecuta el pipeline de Fase 3: triaje normativo básico.

    Args:
        expediente_path:     Ruta al directorio del expediente.
        phase1_result_path:  Ruta explícita a phase1_result.json. Si None,
                             busca en control_interno/phase1_result.json.
        phase2_result_path:  Ruta explícita a phase2_result.json. Si None,
                             busca en control_interno/phase2_result.json.
                             Opcional: si no existe, se continúa sin scope.
        write_outputs:       Si True, escribe phase3_result.json y
                             nota_encuadre_legal.md en output_dir.
        output_dir:          Subdirectorio relativo al expediente (default
                             "control_interno").

    Returns:
        Phase3Result con normativa detectada, procedimiento EIA preliminar,
        cautelas y avisos.

    Raises:
        FileNotFoundError: si phase1_result.json no existe.
    """
    exp_path = Path(expediente_path)
    expediente_id = exp_path.name
    warnings: list[str] = []
    notes: list[str] = []

    # 1. Cargar phase1_result.json (requerido)
    p1_path = (
        Path(phase1_result_path)
        if phase1_result_path is not None
        else exp_path / output_dir / "phase1_result.json"
    )
    if not p1_path.exists():
        raise FileNotFoundError(
            f"phase1_result.json no encontrado en: {p1_path}\n"
            "Ejecute primero:\n"
            f"  python run_expediente.py {exp_path.name} phase1 --write\n"
            "o pase una ruta explícita via phase1_result_path."
        )
    try:
        with open(p1_path, encoding="utf-8") as f:
            phase1_data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en {p1_path}: {exc}") from exc

    candidate_facts: list[dict] = phase1_data.get("candidate_facts", [])
    if phase1_data.get("warnings"):
        warnings.extend(f"[Fase 1] {w}" for w in phase1_data["warnings"])

    # 2. Cargar phase2_result.json (opcional)
    p2_path = (
        Path(phase2_result_path)
        if phase2_result_path is not None
        else exp_path / output_dir / "phase2_result.json"
    )
    object_scope: dict = {}
    if p2_path.exists():
        try:
            with open(p2_path, encoding="utf-8") as f:
                phase2_data = json.load(f)
            object_scope = phase2_data.get("object_scope", {})
            if phase2_data.get("warnings"):
                warnings.extend(f"[Fase 2] {w}" for w in phase2_data["warnings"])
        except json.JSONDecodeError as exc:
            warnings.append(f"phase2_result.json con JSON inválido ({exc}); ignorado.")
    else:
        notes.append(
            "phase2_result.json no encontrado; ObjectScope vacío. "
            "Ejecute fase2 para mejorar la cobertura del triaje."
        )

    # 3. Construir corpus de texto
    text_corpus = _build_text_corpus(candidate_facts, object_scope)

    # 4. Ejecutar detecciones
    has_residuos, residuos_src = _detect_residuos(candidate_facts, text_corpus)
    has_ruido, ruido_src = _detect_ruido(candidate_facts, text_corpus)
    has_natura, natura_src = _detect_natura(text_corpus)
    has_patrimonio, patrimonio_src = _detect_patrimonio(text_corpus)
    has_canarias, canarias_src = _detect_canarias(object_scope, text_corpus)
    has_urbanismo, urbanismo_src = _detect_urbanismo(
        candidate_facts, object_scope, text_corpus
    )
    has_alta_capacidad, alta_cap_src = _detect_alta_capacidad(object_scope, text_corpus)

    # 5. Construir normativa
    normativa = _build_normativa(
        has_residuos=has_residuos,
        residuos_source=residuos_src,
        has_ruido=has_ruido,
        ruido_source=ruido_src,
        has_natura=has_natura,
        natura_source=natura_src,
        has_patrimonio=has_patrimonio,
        patrimonio_source=patrimonio_src,
        has_canarias=has_canarias,
        canarias_source=canarias_src,
        has_urbanismo=has_urbanismo,
        urbanismo_source=urbanismo_src,
    )

    # 6. Determinar procedimiento
    procedimiento, razones = _determine_procedimiento(
        has_residuos=has_residuos,
        has_alta_capacidad=has_alta_capacidad,
        alta_capacidad_source=alta_cap_src,
        candidate_facts=candidate_facts,
        object_scope=object_scope,
    )

    # 7. Cautelas
    cautelas = _build_cautelas(
        object_scope=object_scope,
        has_natura=has_natura,
        has_canarias=has_canarias,
        procedimiento=procedimiento,
    )

    # 8. Construir resultado
    result = Phase3Result(
        expediente_id=expediente_id,
        normativa=normativa,
        procedimiento_eia=procedimiento,
        razones_procedimiento=razones,
        cautelas=cautelas,
        warnings=warnings,
        notes=notes,
    )

    # 9. Escritura opcional
    if write_outputs:
        _write_phase3_outputs(result, exp_path / output_dir)

    return result
