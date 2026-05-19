"""
project_action_builder -- IM-02
Constructor de acciones del proyecto (ProjectAction) desde datos de Fase 2.

Lee los outputs de Fase 2 (phase2_result.json / object_scope) para detectar,
mediante análisis textual determinista, las operaciones presentes en la actividad
del promotor y construye una lista ordenada de ProjectAction para Fase 6.

Restricciones del módulo:
  - No crea EnvironmentalImpact.
  - No valora impactos (sin cálculo Conesa).
  - No crea MitigationMeasure.
  - No crea PVAProgram.
  - No usa IA.
  - No consulta fuentes externas.
  - No hace llamadas a APIs.
  - No escribe archivos (la escritura es responsabilidad del llamador o de la CLI).

Detecta 7 grupos de acciones potenciales:
  1. Recepción y almacenamiento temporal (R13/R1301/R1302)
  2. Clasificación y separación (R1201)
  3. Tratamiento mecánico (R1203, trituración, molino, cizalla...)
  4. Carga, descarga y expedición (transporte, carretilla, camión...)
  5. Maquinaria auxiliar y servicios de apoyo (compresor, báscula, diesel...)
  6. Gestión de residuos peligrosos propios (aceites, baterías, RAEE, LER*)
  7. Cese, limpieza final o retirada

Si no detecta ningún grupo, genera una acción mínima (AC-001) con aviso.

Depende de:
  IM-00 (impact_model) — ProjectAction, Phase6Model, build_empty_phase6_model
  IV-00 (inventory_model) — InventorySummary (opcional)
"""
from __future__ import annotations

import dataclasses
import re
import unicodedata
from dataclasses import dataclass, field

from eia_agent.core.impact_model import (
    Phase6Model,
    ProjectAction,
    build_empty_phase6_model,
)
from eia_agent.core.inventory_model import InventorySummary

# ---------------------------------------------------------------------------
# Constantes de detección
# ---------------------------------------------------------------------------

# Claves de dict cuyo valor es texto relevante para la detección
_TEXT_KEYS: frozenset[str] = frozenset({
    "object_scope",
    "ficha_objeto_evaluado",
    "operaciones_incluidas",
    "operaciones_excluidas",
    "operaciones",
    "actividad",
    "actividades",
    "maquinaria",
    "equipos",
    "capacidad",
    "residuos",
    "ler",
    "notes",
    "warnings",
    "scope",
    "datos",
    "description",
    "descripcion",
    "denominacion",
    "materiales",
    "nombre_proyecto",
})

# Grupos de detección: {clave_grupo: [términos_normalizados]}
# Los términos no llevan acentos (el texto se normaliza antes de comparar).
_DETECTION_GROUPS: dict[str, list[str]] = {
    "recepcion_almacenamiento": [
        "recepci",          # recepción/recepcion
        "almacenamiento",
        "acopio",
        "entrada de residuos",
        "r1302",
        "r1301",
        "r13",
    ],
    "clasificacion_separacion": [
        "clasificaci",      # clasificación/clasificacion
        "separaci",         # separación/separacion
        "selecci",          # selección/seleccion
        "triaje",
        "r1201",
    ],
    "tratamiento_mecanico": [
        "trituraci",        # trituración/trituracion
        "triturado",
        "molino",
        "cizalla",
        "corte",
        "prensa",
        "compactaci",       # compactación/compactacion
        "cribado",
        "r1203",
    ],
    "carga_descarga_transporte": [
        "carga",
        "descarga",
        "expedici",         # expedición/expedicion
        "transporte",
        "camion",           # camión normalizado
        "carretilla",
    ],
    "maquinaria_auxiliar": [
        "compresor",
        "bascula",          # báscula normalizado
        "maquinaria",
        "equipo",
        "motor",
        "diesel",
        "electricidad",
    ],
    "gestion_residuos_peligrosos": [
        "residuo peligroso",
        "residuos peligrosos",
        "aceite",
        "absorbente",
        "filtro",
        "bateria",          # batería normalizado
        "raee",
        "ler*",             # código LER con asterisco literal
    ],
    "cese_limpieza": [
        "cese",
        "desmantelamiento",
        "limpieza final",
        "retirada",
        "clausura",
    ],
}

# Patrón LER peligroso: código de 6 dígitos con espacios opcional + asterisco
# Ejemplo: "16 06 01*" o "160601*"
_LER_HAZARDOUS_PATTERN = re.compile(r"\d{2}\s*\d{2}\s*\d{2}\s*\*")

# Configuración de acciones por grupo
_ACTION_CONFIGS: dict[str, dict] = {
    "recepcion_almacenamiento": {
        "name": "Recepción y almacenamiento temporal de residuos",
        "description": (
            "Recepción en el emplazamiento de residuos procedentes del exterior, "
            "pesaje, registro y almacenamiento temporal previo a su tratamiento. "
            "Genera presiones sobre el suelo, el agua subterránea y el entorno próximo."
        ),
        "action_type": "ALMACENAMIENTO",
        "operation_code": "R13",
    },
    "clasificacion_separacion": {
        "name": "Clasificación y separación de residuos",
        "description": (
            "Separación manual o mecánica de residuos por fracciones o materiales. "
            "Incluye clasificación visual, triaje y separación de corrientes de residuos. "
            "Genera presiones sobre el suelo, la calidad del aire y el entorno acústico."
        ),
        "action_type": "OPERACION",
        "operation_code": "R1201",
    },
    "tratamiento_mecanico": {
        "name": "Tratamiento mecánico de residuos",
        "description": (
            "Operaciones de reducción de tamaño, fragmentación, cribado o compactación "
            "de residuos mediante maquinaria especializada. "
            "Genera presiones sobre la calidad del aire, el entorno acústico y el suelo."
        ),
        "action_type": "OPERACION",
        "operation_code": "R1203",
    },
    "carga_descarga_transporte": {
        "name": "Carga, descarga y expedición de materiales",
        "description": (
            "Movimientos de materiales dentro del emplazamiento y en sus accesos. "
            "Incluye carga de vehículos, descarga de entradas y expedición de salidas. "
            "Genera presiones sobre la calidad del aire, el entorno acústico y el suelo."
        ),
        "action_type": "TRANSPORTE",
        "operation_code": "",
    },
    "maquinaria_auxiliar": {
        "name": "Maquinaria auxiliar y servicios de apoyo",
        "description": (
            "Operación de maquinaria de apoyo: compresores, básculas, equipos de elevación, "
            "sistemas eléctricos y servicios auxiliares de la instalación. "
            "Genera presiones menores sobre el entorno acústico y el consumo energético."
        ),
        "action_type": "AUXILIAR",
        "operation_code": "",
    },
    "gestion_residuos_peligrosos": {
        "name": "Gestión de residuos peligrosos propios de la actividad",
        "description": (
            "Generación, almacenamiento en lugar apropiado y entrega a gestor autorizado "
            "de los residuos peligrosos propios de la actividad: aceites usados, filtros, "
            "baterías, RAEE y otros con código LER de asterisco. "
            "Genera presiones sobre el suelo y las aguas subterráneas."
        ),
        "action_type": "MANTENIMIENTO",
        "operation_code": "",
    },
    "cese_limpieza": {
        "name": "Cese, limpieza final o retirada de la actividad",
        "description": (
            "Operaciones de cierre, desmantelamiento de instalaciones, retirada de residuos "
            "almacenados y restauración de la parcela al término de la vida útil de la actividad. "
            "Genera presiones sobre el suelo y produce residuos de derribo."
        ),
        "action_type": "CESE",
        "operation_code": "",
    },
}

# Acción mínima cuando no se detecta ningún grupo
_MINIMAL_ACTION_NAME = "Funcionamiento general de la actividad"
_MINIMAL_ACTION_DESCRIPTION = (
    "Actividad general de la instalación según la documentación disponible en Fase 2. "
    "No se han detectado operaciones específicas en los datos aportados."
)


# ---------------------------------------------------------------------------
# Dataclass resultado
# ---------------------------------------------------------------------------

@dataclass
class ProjectActionBuildResult:
    """Resultado del constructor de acciones de Fase 6 (IM-02).

    Campos:
        actions:  Lista de ProjectAction detectadas desde Fase 2.
        warnings: Avisos metodológicos (p.ej. sin datos, acción mínima generada).
        notes:    Notas de trazabilidad del proceso de detección.
    """

    actions: list[ProjectAction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "actions": [a.to_dict() for a in self.actions],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [
            f"ProjectActionBuildResult: {len(self.actions)} "
            f"acción{'es' if len(self.actions) != 1 else ''} detectada{'s' if len(self.actions) != 1 else ''}."
        ]
        for a in self.actions:
            op = f" [{a.operation_code}]" if a.operation_code else ""
            lines.append(f"  {a.action_id} — {a.name} ({a.action_type}){op}")
        for w in self.warnings:
            lines.append(f"  AVISO: {w}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Normalización de texto
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Elimina acentos y convierte a minúsculas para comparación robusta."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()


# ---------------------------------------------------------------------------
# Extractor de texto recursivo
# ---------------------------------------------------------------------------

def _collect_text(node: object, parts: list[str], depth: int = 0) -> None:
    """Recorre recursivamente un nodo (dict, list, str) y extrae texto de claves relevantes.

    - Si el nodo es str: lo añade a parts si hay contenido.
    - Si el nodo es list: recursa en cada elemento.
    - Si el nodo es dict: para cada clave, si está en _TEXT_KEYS extrae TODO el texto
      de su valor; si no está en _TEXT_KEYS pero el valor es dict/list, recursa para
      encontrar claves relevantes más profundas.
    """
    if depth > 8:
        return
    if isinstance(node, str):
        stripped = node.strip()
        if stripped:
            parts.append(stripped)
    elif isinstance(node, list):
        for item in node:
            _collect_text(item, parts, depth + 1)
    elif isinstance(node, dict):
        for k, v in node.items():
            if k.lower() in _TEXT_KEYS or k in _TEXT_KEYS:
                _collect_text(v, parts, depth + 1)
            elif isinstance(v, (dict, list)):
                _collect_text(v, parts, depth + 1)


def extract_project_action_text(phase2_data: dict | None = None) -> str:
    """Extrae y normaliza texto relevante de phase2_data para detección de acciones.

    Recorre recursivamente dicts/listas extrayendo texto de claves relevantes.
    El texto resultante está en minúsculas y sin acentos para comparación robusta.

    No falla si phase2_data es None, vacío o tiene estructura inesperada.

    Args:
        phase2_data: Dict con los datos de Fase 2. Puede ser None.

    Returns:
        Cadena normalizada (sin acentos, en minúsculas) con todo el texto relevante.
    """
    if not phase2_data:
        return ""
    parts: list[str] = []
    _collect_text(phase2_data, parts)
    raw = " ".join(parts)
    return _normalize(raw)


# ---------------------------------------------------------------------------
# Detector de operaciones
# ---------------------------------------------------------------------------

def detect_project_operations(text: str) -> dict[str, list[str]]:
    """Detecta términos de operaciones por grupo en el texto normalizado.

    El texto debe estar ya normalizado (lowercase, sin acentos).
    Usa presencia textual simple: sin IA, sin interpretación semántica.

    También detecta códigos LER peligrosos (patrón XX XX XX*) y los añade
    al grupo gestion_residuos_peligrosos.

    Args:
        text: Texto normalizado a analizar.

    Returns:
        Dict {grupo: [términos_detectados]}. Cada grupo tiene su lista
        (vacía si no se detectó ningún término del grupo).
    """
    result: dict[str, list[str]] = {}

    for group_key, terms in _DETECTION_GROUPS.items():
        found: list[str] = []
        for term in terms:
            if term in text:
                found.append(term)
        result[group_key] = found

    # Detección especial: código LER peligroso (e.g. "16 06 01*")
    if _LER_HAZARDOUS_PATTERN.search(text):
        hazardous = result.get("gestion_residuos_peligrosos", [])
        if "ler_codigo_peligroso" not in hazardous:
            hazardous = list(hazardous)
            hazardous.append("ler_codigo_peligroso")
        result["gestion_residuos_peligrosos"] = hazardous

    return result


# ---------------------------------------------------------------------------
# Constructor principal
# ---------------------------------------------------------------------------

def _make_source_refs(phase2_data: dict | None) -> list[str]:
    """Construye lista de referencias a las fuentes detectadas."""
    refs: list[str] = ["phase2_result"]
    if phase2_data:
        scope = phase2_data.get("object_scope") or {}
        if scope.get("operaciones_incluidas"):
            if "object_scope" not in refs:
                refs.append("object_scope")
        fuentes = scope.get("fuentes") or []
        if fuentes and "documentación del promotor" not in refs:
            refs.append("documentación del promotor")
    return refs


def build_actions_from_phase2_data(
    phase2_data: dict | None = None,
) -> ProjectActionBuildResult:
    """Construye lista de ProjectAction a partir de datos de Fase 2.

    Extrae texto, detecta operaciones por grupo y construye una acción ordenada
    por cada grupo con indicios textuales. Si no detecta ninguna operación,
    genera una acción mínima AC-001 con aviso metodológico.

    No crea EnvironmentalImpact, no valora impactos, no genera medidas ni PVA.

    Args:
        phase2_data: Dict con los datos de Fase 2 (phase2_result.json parseado).
                     Puede ser None si no hay datos disponibles.

    Returns:
        ProjectActionBuildResult con acciones, avisos y notas de trazabilidad.
    """
    warnings_out: list[str] = []
    notes_out: list[str] = []

    text = extract_project_action_text(phase2_data)
    detected = detect_project_operations(text)
    source_refs = _make_source_refs(phase2_data)

    actions: list[ProjectAction] = []
    counter = 1

    # Mantener el orden de los grupos para IDs correlativos predecibles
    group_order = list(_DETECTION_GROUPS.keys())

    for group_key in group_order:
        found_terms = detected.get(group_key, [])
        if not found_terms:
            continue

        cfg = _ACTION_CONFIGS[group_key]
        action_id = f"AC-{counter:03d}"
        counter += 1

        # Afinar operation_code con el término más específico detectado
        operation_code = cfg.get("operation_code", "")
        if group_key == "recepcion_almacenamiento":
            if "r1302" in found_terms:
                operation_code = "R1302"
            elif "r1301" in found_terms:
                operation_code = "R1301"
            elif "r13" in found_terms:
                operation_code = "R13"
        elif group_key == "clasificacion_separacion":
            if "r1201" in found_terms:
                operation_code = "R1201"
        elif group_key == "tratamiento_mecanico":
            if "r1203" in found_terms:
                operation_code = "R1203"

        action_notes = [
            f"Términos detectados en datos de Fase 2: {', '.join(found_terms[:10])}"
        ]

        actions.append(
            ProjectAction(
                action_id=action_id,
                name=cfg["name"],
                description=cfg["description"],
                action_type=cfg["action_type"],
                operation_code=operation_code,
                source_refs=list(source_refs),
                notes=action_notes,
            )
        )

    if not actions:
        # Sin detecciones: generar acción mínima
        actions.append(
            ProjectAction(
                action_id="AC-001",
                name=_MINIMAL_ACTION_NAME,
                description=_MINIMAL_ACTION_DESCRIPTION,
                action_type="OTRO",
                operation_code="",
                source_refs=list(source_refs),
                notes=[
                    "Acción mínima generada automáticamente. "
                    "No se detectaron términos de operaciones específicas en Fase 2."
                ],
            )
        )
        warnings_out.append(
            "No se han detectado operaciones específicas en los datos de Fase 2. "
            "Se genera una acción mínima (AC-001, tipo OTRO). "
            "Revisar y completar con datos del promotor."
        )
    else:
        notes_out.append(
            f"IM-02: {len(actions)} acción(es) detectada(s) desde datos de Fase 2. "
            "Revisar y complementar con el técnico responsable del expediente."
        )

    if not phase2_data:
        warnings_out.append(
            "No se han proporcionado datos de Fase 2 (phase2_data=None). "
            "Las acciones se generan sin información de las operaciones declaradas."
        )

    return ProjectActionBuildResult(
        actions=actions,
        warnings=warnings_out,
        notes=notes_out,
    )


# ---------------------------------------------------------------------------
# Integración con Phase6Model
# ---------------------------------------------------------------------------

def merge_actions_into_phase6_model(
    model: Phase6Model,
    actions: list[ProjectAction],
) -> Phase6Model:
    """Sustituye las acciones de un Phase6Model por una nueva lista.

    No muta el modelo original. Usa dataclasses.replace() para clonar.
    Conserva receptor_factors, impacts, measures y pva_programs intactos.

    Args:
        model:   Phase6Model original (no se modifica).
        actions: Nueva lista de ProjectAction a asignar.

    Returns:
        Nueva instancia de Phase6Model con las acciones actualizadas.
    """
    return dataclasses.replace(model, actions=list(actions))


def build_phase6_model_with_actions(
    expediente_id: str,
    phase2_data: dict | None = None,
    inventory_summary: InventorySummary | None = None,
) -> Phase6Model:
    """Crea un Phase6Model con acciones desde Fase 2 y factores receptores opcionales.

    No crea EnvironmentalImpact, MitigationMeasure ni PVAProgram.

    Args:
        expediente_id:      ID del expediente (e.g. "expediente-EIA-2026-...").
        phase2_data:        Dict con datos de Fase 2. Puede ser None.
        inventory_summary:  InventorySummary de Fase 5. Si se proporciona,
                            puebla receptor_factors. Puede ser None.

    Returns:
        Phase6Model con actions y (opcionalmente) receptor_factors.
        impacts, measures y pva_programs siempre vacíos.
    """
    model = build_empty_phase6_model(expediente_id, inventory_summary)
    build_result = build_actions_from_phase2_data(phase2_data)
    return merge_actions_into_phase6_model(model, build_result.actions)
