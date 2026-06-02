"""
client_action_plan -- plan operativo para cerrar un Documento Ambiental.

Convierte auditorias y estado DA-01 en dos listas separadas:
  - documentacion o aclaraciones que conviene pedir al promotor;
  - acciones internas del equipo tecnico.

No declara aptitud administrativa y no cierra gaps. Es una capa de producto
para que el usuario final sepa que pedir y que corregir a continuacion.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ACTION_PLAN_JSON = "plan_accion_cliente.json"
ACTION_PLAN_MD = "plan_accion_cliente.md"

DISCLAIMER = (
    "Este plan no declara el expediente apto para presentacion administrativa. "
    "Solo ordena pendientes y acciones de cierre."
)


@dataclass
class ClientActionItem:
    """Accion concreta para promotor o equipo tecnico."""

    action_id: str
    audience: str  # PROMOTOR | EQUIPO_TECNICO
    priority: str  # ALTA | MEDIA | BAJA
    title: str
    reason: str
    expected_format: str
    source: str
    reference: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "audience": self.audience,
            "priority": self.priority,
            "title": self.title,
            "reason": self.reason,
            "expected_format": self.expected_format,
            "source": self.source,
            "reference": self.reference,
            "recommendation": self.recommendation,
        }


@dataclass
class ClientActionPlan:
    """Resultado del plan de accion del expediente."""

    expediente_id: str
    administrative_ready: bool = False
    promoter_requests: list[ClientActionItem] = field(default_factory=list)
    technical_actions: list[ClientActionItem] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def has_high_priority(self) -> bool:
        return any(i.priority == "ALTA" for i in self.promoter_requests + self.technical_actions)

    def promoter_high_count(self) -> int:
        return sum(1 for i in self.promoter_requests if i.priority == "ALTA")

    def technical_high_count(self) -> int:
        return sum(1 for i in self.technical_actions if i.priority == "ALTA")

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "administrative_ready": self.administrative_ready,
            "executive_summary": _build_executive_summary(self),
            "promoter_requests": [i.to_dict() for i in self.promoter_requests],
            "technical_actions": [i.to_dict() for i in self.technical_actions],
            "closing_route": _build_closing_route_steps(self),
            "counts": {
                "promoter_requests": len(self.promoter_requests),
                "promoter_high": self.promoter_high_count(),
                "technical_actions": len(self.technical_actions),
                "technical_high": self.technical_high_count(),
            },
            "source_files": list(self.source_files),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "disclaimer": DISCLAIMER,
        }

    def summary(self) -> str:
        return "\n".join([
            f"--- Plan de accion cliente [{self.expediente_id}] ---",
            f"Peticiones al promotor : {len(self.promoter_requests)} "
            f"(ALTA: {self.promoter_high_count()})",
            f"Acciones tecnicas      : {len(self.technical_actions)} "
            f"(ALTA: {self.technical_high_count()})",
            f"Admin ready            : {self.administrative_ready}",
            f"NOTA: {DISCLAIMER}",
        ])


def _safe_load_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _priority_from_severity(severity: str) -> str:
    sev = str(severity or "").upper()
    if sev in {"BLOQUEANTE", "ALTA", "ERROR"}:
        return "ALTA"
    if sev in {"MEDIA", "WARNING", "WARN"}:
        return "MEDIA"
    return "BAJA"


def _clean(text: Any, default: str = "") -> str:
    return str(text if text is not None else default).strip()


def _template_for_art45(requirement: str, message: str) -> dict[str, str]:
    req = requirement.upper()
    if req == "ART45-03":
        return {
            "title": "Analisis de alternativas y justificacion de la solucion adoptada",
            "expected_format": (
                "Memoria tecnica o anexo firmado con alternativa cero, alternativas "
                "razonables estudiadas, alternativa seleccionada y justificacion ambiental."
            ),
            "recommendation": (
                "Aportar una comparativa clara de alternativas, indicando por que se "
                "descartan y por que la solucion elegida es la preferente."
            ),
        }
    if req == "ART45-10":
        return {
            "title": "Cartografia y ubicacion suficiente del proyecto",
            "expected_format": (
                "Planos georreferenciados, coordenadas WGS84 y REGCAN95/UTM huso 28N, "
                "delimitacion de parcela/actuacion y, si existe, SHP/GeoJSON/DXF."
            ),
            "recommendation": (
                "Aportar cartografia de situacion, emplazamiento, Red Natura/ENP, usos "
                "del suelo y riesgos fisicos con escala y fuente."
            ),
        }
    if req == "ART45-01":
        return {
            "title": "Motivacion del procedimiento de evaluacion ambiental simplificada",
            "expected_format": "Nota tecnica o apartado de memoria con encuadre procedimental.",
            "recommendation": "Justificar expresamente la aplicacion del procedimiento simplificado.",
        }
    if req == "ART45-09":
        return {
            "title": "Vulnerabilidad ante riesgos de accidentes graves o catastrofes",
            "expected_format": "Apartado tecnico con riesgos naturales/tecnologicos y medidas asociadas.",
            "recommendation": "Completar la evaluacion de vulnerabilidad y su reflejo en impactos.",
        }
    if req == "ART45-12":
        return {
            "title": "Resumen no tecnico",
            "expected_format": "Resumen no tecnico revisable en lenguaje claro.",
            "recommendation": "Preparar una version no tecnica consistente con el documento principal.",
        }
    return {
        "title": f"Completar requisito {req or 'ambiental'}",
        "expected_format": "Documento tecnico, plano o aclaracion firmada segun proceda.",
        "recommendation": "Completar el requisito indicado por la auditoria.",
    }


def _is_promoter_issue(issue: dict[str, Any]) -> bool:
    req = _clean(issue.get("related_requirement")).upper()
    msg = _clean(issue.get("message")).lower()
    if req in {"ART45-03", "ART45-10"}:
        return True
    promoter_terms = (
        "coordenada", "cartografia", "plano", "shp", "geojson", "dxf",
        "alternativa", "memoria tecnica", "autorizacion", "referencia catastral",
        "promotor", "titular", "documentacion aportada",
    )
    internal_terms = (
        "frase prohibida", "lenguaje", "bloque", "qc", "docx", "indice",
        "hoja de firmas", "trazabilidad", "coherencia entre bloques",
    )
    return any(t in msg for t in promoter_terms) and not any(t in msg for t in internal_terms)


def _item_from_audit_issue(issue: dict[str, Any], index: int) -> ClientActionItem:
    req = _clean(issue.get("related_requirement"))
    template = _template_for_art45(req, _clean(issue.get("message")))
    audience = "PROMOTOR" if _is_promoter_issue(issue) else "EQUIPO_TECNICO"
    priority = _priority_from_severity(_clean(issue.get("severity")))
    title = template["title"] if req else _clean(issue.get("code"), "Revision tecnica")
    if audience == "EQUIPO_TECNICO" and "frase prohibida" in _clean(issue.get("message")).lower():
        title = "Revisar lenguaje prudente del Documento Ambiental"
    return ClientActionItem(
        action_id=f"ACP-{index:03d}",
        audience=audience,
        priority=priority,
        title=title,
        reason=_clean(issue.get("message"), "Incidencia detectada en auditoria."),
        expected_format=template["expected_format"] if audience == "PROMOTOR" else "Correccion interna del expediente y regeneracion de auditorias.",
        source=_clean(issue.get("source"), "final_audit_result"),
        reference=req or _clean(issue.get("related_file")),
        recommendation=_clean(issue.get("recommendation"), template["recommendation"]),
    )


def _item_from_da_state(raw: dict[str, Any], index: int) -> ClientActionItem:
    text = " ".join([
        _clean(raw.get("item")),
        _clean(raw.get("accion")),
        _clean(raw.get("valor")),
    ])
    req = ""
    for candidate in ("ART45-03", "ART45-10", "ART45-01", "ART45-09", "ART45-12"):
        if candidate in text:
            req = candidate
            break
    template = _template_for_art45(req, text)
    priority = "ALTA" if _clean(raw.get("categoria")).upper() == "BLOQUEANTE" else "MEDIA"
    audience = "PROMOTOR" if req in {"ART45-03", "ART45-10"} else "EQUIPO_TECNICO"
    return ClientActionItem(
        action_id=f"ACP-{index:03d}",
        audience=audience,
        priority=priority,
        title=template["title"],
        reason=_clean(raw.get("accion"), _clean(raw.get("item"), "Pendiente detectado.")),
        expected_format=template["expected_format"] if audience == "PROMOTOR" else "Revision tecnica interna.",
        source=_clean(raw.get("fuente"), "estado_expediente_da"),
        reference=req or _clean(raw.get("item")),
        recommendation=template["recommendation"],
    )


def _dedupe_items(items: list[ClientActionItem]) -> list[ClientActionItem]:
    by_key: dict[tuple[str, str, str], ClientActionItem] = {}
    priority_rank = {"ALTA": 3, "MEDIA": 2, "BAJA": 1}
    for item in items:
        key = (item.audience, item.reference or item.title, item.title)
        existing = by_key.get(key)
        if existing is None or priority_rank[item.priority] > priority_rank[existing.priority]:
            by_key[key] = item
    result = list(by_key.values())
    for idx, item in enumerate(result, 1):
        item.action_id = f"ACP-{idx:03d}"
    return result


def _group_recommendation(source: str, source_items: list[ClientActionItem]) -> str:
    """Construye una recomendacion ejecutiva para incidencias agrupadas."""
    if not source_items:
        return ""

    messages = " ".join([
        " ".join([i.reason, i.recommendation, i.reference]).lower()
        for i in source_items
    ])

    if source == "RD-04_BLOCK_CONSISTENCY":
        advice: list[str] = []
        if any(t in messages for t in ("diagnostica", "estudio acustico", "medicion acustica")):
            advice.append(
                "Medidas diagnosticas: sustituir cualquier redaccion que las presente "
                "como reductoras por una formulacion de condicion previa/verificacion. "
                "Ejemplo seguro: 'El estudio acustico no reduce por si solo la "
                "significancia; dimensiona y verifica medidas materiales como "
                "insonorizacion, encapsulamiento o limitacion horaria'."
            )
        if any(t in messages for t in ("prl", "epi", "proteccion auditiva", "auricular")):
            advice.append(
                "PRL/EPI: separar la proteccion de trabajadores de las medidas "
                "ambientales exteriores. Los EPI no computan como medida correctora "
                "del impacto ambiental."
            )
        if any(t in messages for t in ("red natura", "zepa", "zec", "lic")):
            advice.append(
                "Red Natura/ENP: mantener la misma conclusion y cautelas en inventario, "
                "impactos, medidas, PVA y conclusiones, diferenciando dato consultado "
                "de interpretacion tecnica."
            )
        if any(t in messages for t in ("patrimonio", "arqueolog")):
            advice.append(
                "Patrimonio: alinear inventario, impacto, medida documental y PVA; si "
                "falta consulta oficial, dejar el impacto condicionado o pendiente."
            )
        if not advice:
            advice.append(
                "Revisar bloque por bloque la misma afirmacion tecnica y mantener "
                "identico alcance, cautelas, estado de evidencia y medidas asociadas."
            )
        return " ".join(advice)

    if source == "AU-03_TRACEABILITY":
        return (
            "Anadir o corregir referencias cruzadas entre hechos, impactos, medidas, "
            "PVA y anexos. Cada afirmacion relevante debe poder rastrearse hasta una "
            "fuente, ficha o output tecnico."
        )

    if source == "AU-02_PRUDENCE":
        return (
            "Sustituir afirmaciones absolutas por lenguaje prudente y trazable: "
            "'no se detecta en las fuentes consultadas', 'segun la documentacion "
            "analizada' o 'pendiente de prospeccion/consulta'."
        )

    if source == "RD-09_PRL_MEASURES":
        return (
            "Separar las medidas PRL de las medidas ambientales. Si un impacto "
            "ambiental necesita reduccion, debe existir una medida preventiva, "
            "correctora o protectora EIA independiente."
        )

    return source_items[0].recommendation


def _group_technical_actions(items: list[ClientActionItem]) -> list[ClientActionItem]:
    """Agrupa auditorias internas repetitivas para que el plan sea usable."""
    grouped_sources = {
        "AU-02_PRUDENCE": "Revisar lenguaje prudente en el expediente",
        "AU-03_TRACEABILITY": "Completar trazabilidad entre hechos clave y documento",
        "RD-04_BLOCK_CONSISTENCY": "Resolver incoherencias entre bloques",
        "RD-09_PRL_MEASURES": "Separar medidas ambientales y medidas PRL",
        "pipeline": "Revisar advertencias del pipeline tecnico",
        "DOCUMENT_STRUCTURE": "Revisar estructura formal del DOCX",
        "DOCUMENT_PRESENTATION": "Revisar preparacion para firma y presentacion",
    }
    priority_rank = {"ALTA": 3, "MEDIA": 2, "BAJA": 1}
    buckets: dict[str, list[ClientActionItem]] = {}
    passthrough: list[ClientActionItem] = []

    for item in items:
        if item.source in grouped_sources:
            buckets.setdefault(item.source, []).append(item)
        else:
            passthrough.append(item)

    result = list(passthrough)
    for source, source_items in buckets.items():
        priority = max(source_items, key=lambda i: priority_rank.get(i.priority, 0)).priority
        references = [i.reference for i in source_items if i.reference]
        sample_refs = ", ".join(references[:5])
        extra = f" Referencias principales: {sample_refs}." if sample_refs else ""
        result.append(ClientActionItem(
            action_id="ACP-000",
            audience="EQUIPO_TECNICO",
            priority=priority,
            title=grouped_sources[source],
            reason=f"Se detectan {len(source_items)} incidencia(s) internas asociadas a {source}.{extra}",
            expected_format="Correccion interna del expediente, regeneracion de outputs y nueva auditoria.",
            source=source,
            reference=source,
            recommendation=_group_recommendation(source, source_items),
        ))

    result.sort(key=lambda i: (-priority_rank.get(i.priority, 0), i.source, i.title))
    for idx, item in enumerate(result, 1):
        item.action_id = f"ACP-{idx:03d}"
    return result


def _renumber_items(items: list[ClientActionItem], prefix: str = "ACP") -> None:
    for idx, item in enumerate(items, 1):
        item.action_id = f"{prefix}-{idx:03d}"


def _build_closing_route_steps(plan: ClientActionPlan) -> list[dict[str, Any]]:
    """Devuelve la ruta de cierre en formato estructurado para UI/API."""
    promoter_high = [i for i in plan.promoter_requests if i.priority == "ALTA"]
    technical_high = [i for i in plan.technical_actions if i.priority == "ALTA"]
    promoter_rest = [i for i in plan.promoter_requests if i.priority != "ALTA"]
    technical_rest = [i for i in plan.technical_actions if i.priority != "ALTA"]

    steps: list[dict[str, Any]] = []

    def add_step(title: str, audience: str, priority: str, action_refs: list[str]) -> None:
        steps.append({
            "order": len(steps) + 1,
            "title": title,
            "audience": audience,
            "priority": priority,
            "action_refs": action_refs,
        })

    if not any([promoter_high, technical_high, promoter_rest, technical_rest]):
        add_step(
            "Ejecutar de nuevo las auditorias cuando existan outputs del expediente.",
            "EQUIPO_TECNICO",
            "MEDIA",
            [],
        )
        return steps

    if promoter_high:
        add_step(
            f"Solicitar al promotor los {len(promoter_high)} item(s) de criticidad ALTA.",
            "PROMOTOR",
            "ALTA",
            [i.action_id for i in promoter_high],
        )
    if technical_high:
        add_step(
            f"Resolver las {len(technical_high)} accion(es) tecnicas ALTA antes de regenerar el documento.",
            "EQUIPO_TECNICO",
            "ALTA",
            [i.action_id for i in technical_high],
        )
    if promoter_rest or technical_rest:
        add_step(
            "Cerrar los pendientes MEDIA/BAJA que condicionan calidad, firma o trazabilidad.",
            "MIXTO",
            "MEDIA",
            [i.action_id for i in promoter_rest + technical_rest],
        )
    add_step(
        "Regenerar Documento Ambiental, paquete documental, plan de accion y auditoria final.",
        "EQUIPO_TECNICO",
        "MEDIA",
        [],
    )
    add_step(
        "Revisar tecnicamente el resultado; este plan no sustituye firma ni validacion juridica.",
        "EQUIPO_TECNICO",
        "MEDIA",
        [],
    )
    return steps


def _build_executive_summary(plan: ClientActionPlan) -> dict[str, Any]:
    """Construye un resumen corto para cabecera de UI o informe ejecutivo."""
    promoter_high = plan.promoter_high_count()
    technical_high = plan.technical_high_count()
    total_high = promoter_high + technical_high
    total_items = len(plan.promoter_requests) + len(plan.technical_actions)

    if total_high:
        status = "BLOQUEADO_POR_ITEMS_ALTA"
        headline = (
            f"Expediente con {total_high} item(s) ALTA pendientes; "
            "no debe considerarse cerrable para presentacion."
        )
        if promoter_high:
            next_action = "Solicitar primero al promotor la documentacion ALTA pendiente."
        else:
            next_action = "Resolver primero las acciones tecnicas ALTA."
    elif total_items:
        status = "PENDIENTES_NO_BLOQUEANTES"
        headline = (
            "Expediente sin items ALTA en el plan, pero con pendientes de calidad "
            "o cierre documental."
        )
        next_action = "Cerrar pendientes MEDIA/BAJA y regenerar auditorias."
    else:
        status = "SIN_ITEMS_DETECTADOS"
        headline = "No hay items accionables detectados con las fuentes disponibles."
        next_action = "Ejecutar o actualizar cliente-da y audit-final si faltan outputs."

    return {
        "status": status,
        "headline": headline,
        "next_action": next_action,
        "has_high_priority": total_high > 0,
        "promoter_high": promoter_high,
        "technical_high": technical_high,
        "total_items": total_items,
        "administrative_ready": False,
    }


def build_client_action_plan(expediente_path: str | Path) -> ClientActionPlan:
    """Construye un plan de accion desde outputs existentes del expediente."""
    exp = Path(expediente_path)
    plan = ClientActionPlan(expediente_id=exp.name)

    audit_path = exp / "auditoria" / "final_audit_result.json"
    state_path = exp / "documento" / "estado_expediente_da.json"
    audit = _safe_load_json(audit_path)
    state = _safe_load_json(state_path)

    if audit:
        plan.source_files.append(str(audit_path.relative_to(exp)))
    if state:
        plan.source_files.append(str(state_path.relative_to(exp)))

    raw_items: list[ClientActionItem] = []
    next_id = 1

    if audit:
        for issue in audit.get("issues", []):
            if not isinstance(issue, dict):
                continue
            priority = _priority_from_severity(_clean(issue.get("severity")))
            if priority not in {"ALTA", "MEDIA"}:
                continue
            raw_items.append(_item_from_audit_issue(issue, next_id))
            next_id += 1

    if state:
        for section in ("estado_bloqueante", "estado_pendiente"):
            for raw in state.get(section, []):
                if isinstance(raw, dict):
                    raw_items.append(_item_from_da_state(raw, next_id))
                    next_id += 1

    if not audit and not state:
        plan.warnings.append(
            "No se encontraron final_audit_result.json ni estado_expediente_da.json. "
            "Ejecute primero cliente-da --write o audit-final --write."
        )

    deduped = _dedupe_items(raw_items)
    plan.promoter_requests = [i for i in deduped if i.audience == "PROMOTOR"]
    plan.technical_actions = _group_technical_actions(
        [i for i in deduped if i.audience == "EQUIPO_TECNICO"]
    )
    _renumber_items(plan.promoter_requests)
    _renumber_items(plan.technical_actions)
    plan.notes.append("Plan generado a partir de auditorias existentes; no modifica el expediente.")
    plan.notes.append("Los items ALTA deben resolverse antes de considerar la presentacion.")
    return plan


def build_client_action_plan_markdown(plan: ClientActionPlan) -> str:
    """Renderiza el plan de accion en Markdown operativo."""
    lines: list[str] = []
    lines.append(f"# Plan de accion cliente — {plan.expediente_id}")
    lines.append("")
    lines.append(f"> **AVISO**: {DISCLAIMER}")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    summary = _build_executive_summary(plan)
    lines.append(f"- Estado operativo: {summary['status']}")
    lines.append(f"- Lectura ejecutiva: {summary['headline']}")
    lines.append(f"- Siguiente accion: {summary['next_action']}")
    lines.append(f"- Peticiones al promotor: {len(plan.promoter_requests)}")
    lines.append(f"- Peticiones ALTA al promotor: {plan.promoter_high_count()}")
    lines.append(f"- Acciones tecnicas internas: {len(plan.technical_actions)}")
    lines.append(f"- Acciones tecnicas ALTA: {plan.technical_high_count()}")
    lines.append("- administrative_ready: false")
    lines.append("")

    lines.extend(_render_closing_route(plan))

    lines.append("## Para pedir al promotor")
    lines.append("")
    if plan.promoter_requests:
        for item in plan.promoter_requests:
            lines.append(f"### {item.action_id} — {item.title}")
            lines.append("")
            lines.append(f"- Criticidad: {item.priority}")
            lines.append(f"- Motivo: {item.reason}")
            lines.append(f"- Formato esperado: {item.expected_format}")
            if item.reference:
                lines.append(f"- Referencia: {item.reference}")
            if item.recommendation:
                lines.append(f"- Recomendacion: {item.recommendation}")
            lines.append("")
    else:
        lines.append("_No se han identificado peticiones directas al promotor._")
        lines.append("")

    lines.append("## Acciones internas del equipo tecnico")
    lines.append("")
    if plan.technical_actions:
        for item in plan.technical_actions:
            lines.append(f"### {item.action_id} — {item.title}")
            lines.append("")
            lines.append(f"- Criticidad: {item.priority}")
            lines.append(f"- Motivo: {item.reason}")
            lines.append(f"- Accion esperada: {item.expected_format}")
            if item.reference:
                lines.append(f"- Referencia: {item.reference}")
            if item.recommendation:
                lines.append(f"- Recomendacion: {item.recommendation}")
            lines.append("")
    else:
        lines.append("_No se han identificado acciones tecnicas internas._")
        lines.append("")

    if plan.promoter_requests:
        lines.append("## Borrador de correo al promotor")
        lines.append("")
        lines.append("```text")
        lines.append(f"Asunto: Solicitud de informacion tecnica — {plan.expediente_id}")
        lines.append("")
        lines.append("Estimado/a:")
        lines.append("")
        lines.append(
            "Tras la revision tecnica del expediente, necesitamos completar la "
            "siguiente documentacion antes de poder cerrar el Documento Ambiental:"
        )
        lines.append("")
        for item in plan.promoter_requests:
            lines.append(f"- {item.title} ({item.priority}): {item.expected_format}")
        lines.append("")
        lines.append(
            "La falta de los items de criticidad ALTA impide cerrar el expediente "
            "para revision tecnica y juridica previa a cualquier tramite."
        )
        lines.append("")
        lines.append("Quedamos a su disposicion para cualquier aclaracion.")
        lines.append("```")
        lines.append("")

    if plan.warnings:
        lines.append("## Avisos")
        lines.append("")
        for warning in plan.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*{DISCLAIMER}*")
    return "\n".join(lines)


def _render_closing_route(plan: ClientActionPlan) -> list[str]:
    """Renderiza una ruta corta y ordenada para cerrar el expediente."""
    lines: list[str] = []
    lines.append("## Ruta recomendada de cierre")
    lines.append("")

    for step in _build_closing_route_steps(plan):
        lines.append(f"{step['order']}. {step['title']}")
    lines.append("")
    return lines


def write_client_action_plan_outputs(
    plan: ClientActionPlan,
    expediente_path: str | Path,
) -> tuple[Path, Path]:
    """Escribe JSON y Markdown del plan en documento/."""
    exp = Path(expediente_path)
    out_dir = exp / "documento"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / ACTION_PLAN_JSON
    md_path = out_dir / ACTION_PLAN_MD
    json_path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_client_action_plan_markdown(plan), encoding="utf-8")
    return json_path, md_path
