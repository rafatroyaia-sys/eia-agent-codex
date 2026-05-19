"""
assumption_test_system -- OB-05
Sistema AT (Asunciones de Test) para EIA-Agent v2.1.

Una Asuncion de Test (AT) desbloquea trabajo tecnico en modo test cuando
falta informacion real, pero impide que el expediente se considere apto
para presentacion administrativa.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No confirma datos.
  - No resuelve gaps.
  - No modifica impactos, medidas ni PVA automaticamente.
  - administrative_ready siempre False mientras existan ATs activas.
  - Una AT activa nunca convierte ninguna referencia en CONFIRMADO.

Uso:
    from eia_agent.core.assumption_test_system import (
        create_assumption_from_gap,
        load_assumptions_registry,
        build_assumptions_markdown,
        assumptions_block_administrative_submission,
    )
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

ASSUMPTION_STATUS: list[str] = [
    "ACTIVA",
    "RESUELTA",
    "DESCARTADA",
    "SUSTITUIDA",
]

ASSUMPTION_SCOPE: list[str] = [
    "OBJETO",
    "INVENTARIO",
    "IMPACTO",
    "MEDIDA",
    "PVA",
    "CARTOGRAFIA",
    "CLIMA",
    "NORMATIVA",
    "AUDITORIA",
    "BLOQUE_REDACCION",
    "GLOBAL",
]

ASSUMPTION_SEVERITY: list[str] = [
    "BLOQUEANTE_REAL",
    "ALTA",
    "MEDIA",
    "BAJA",
]

_AT_ID_RE: re.Pattern = re.compile(r"^AT-\d{3,}$")


# ---------------------------------------------------------------------------
# AsuncionTest
# ---------------------------------------------------------------------------


@dataclass
class AsuncionTest:
    """Asuncion de test: desbloqueo provisional de trabajo tecnico.

    Atributos obligatorios al crear: at_id, title, description, scope,
    severity, status, justification, impide_aptitud_administrativa.
    """

    at_id: str
    title: str
    description: str
    scope: str
    severity: str
    status: str
    justification: str
    impide_aptitud_administrativa: bool
    created_from: str = ""
    resolves_ref: Optional[str] = None
    linked_refs: list[str] = field(default_factory=list)
    affected_phases: list[str] = field(default_factory=list)
    affected_outputs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Valida la AT y devuelve lista de errores (vacia = valida)."""
        errors: list[str] = []

        if not _AT_ID_RE.match(self.at_id):
            errors.append(
                f"at_id invalido: {self.at_id!r} "
                "(formato esperado: AT-001, AT-002...)"
            )
        if not self.title.strip():
            errors.append("title no puede estar vacio")
        if not self.description.strip():
            errors.append("description no puede estar vacia")
        if self.scope not in ASSUMPTION_SCOPE:
            errors.append(
                f"scope invalido: {self.scope!r} "
                f"(valores: {ASSUMPTION_SCOPE})"
            )
        if self.severity not in ASSUMPTION_SEVERITY:
            errors.append(
                f"severity invalida: {self.severity!r} "
                f"(valores: {ASSUMPTION_SEVERITY})"
            )
        if self.status not in ASSUMPTION_STATUS:
            errors.append(
                f"status invalido: {self.status!r} "
                f"(valores: {ASSUMPTION_STATUS})"
            )
        if self.status == "ACTIVA" and not self.impide_aptitud_administrativa:
            errors.append(
                "AT activa debe tener impide_aptitud_administrativa=True"
            )
        if self.status == "ACTIVA" and not self.justification.strip():
            errors.append("AT activa debe tener justification no vacia")

        return errors

    def is_active(self) -> bool:
        """True si la AT esta en estado ACTIVA."""
        return self.status == "ACTIVA"

    def blocks_administrative_submission(self) -> bool:
        """True si esta AT bloquea la aptitud administrativa del expediente.

        Solo las ATs activas con impide_aptitud_administrativa=True bloquean.
        ATs RESUELTA, DESCARTADA o SUSTITUIDA no bloquean.
        """
        return self.impide_aptitud_administrativa and self.status == "ACTIVA"

    def to_dict(self) -> dict:
        return {
            "at_id": self.at_id,
            "title": self.title,
            "description": self.description,
            "resolves_ref": self.resolves_ref,
            "linked_refs": list(self.linked_refs),
            "scope": self.scope,
            "severity": self.severity,
            "status": self.status,
            "justification": self.justification,
            "affected_phases": list(self.affected_phases),
            "affected_outputs": list(self.affected_outputs),
            "impide_aptitud_administrativa": self.impide_aptitud_administrativa,
            "created_from": self.created_from,
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }

    def summary(self) -> str:
        ref = f" -> {self.resolves_ref}" if self.resolves_ref else ""
        return (
            f"{self.at_id} ({self.status}/{self.scope}/{self.severity})"
            f"{ref}: {self.title}"
        )


# ---------------------------------------------------------------------------
# AsuncionTestRegistry
# ---------------------------------------------------------------------------


@dataclass
class AsuncionTestRegistry:
    """Registro de todas las ATs de un expediente."""

    expediente_id: str
    assumptions: list[AsuncionTest] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def active_assumptions(self) -> list[AsuncionTest]:
        """Devuelve las ATs con status ACTIVA."""
        return [a for a in self.assumptions if a.is_active()]

    def resolved_assumptions(self) -> list[AsuncionTest]:
        """Devuelve las ATs con status RESUELTA, DESCARTADA o SUSTITUIDA."""
        return [
            a for a in self.assumptions
            if a.status in ("RESUELTA", "DESCARTADA", "SUSTITUIDA")
        ]

    def blocks_administrative_submission(self) -> bool:
        """True si alguna AT activa bloquea la aptitud administrativa."""
        return any(a.blocks_administrative_submission() for a in self.assumptions)

    def by_scope(self, scope: str) -> list[AsuncionTest]:
        """Devuelve las ATs con el scope indicado."""
        return [a for a in self.assumptions if a.scope == scope]

    def by_ref(self, ref: str) -> list[AsuncionTest]:
        """Devuelve las ATs vinculadas a la referencia indicada."""
        return [
            a for a in self.assumptions
            if a.resolves_ref == ref or ref in a.linked_refs
        ]

    def validate(self) -> list[str]:
        """Valida el registro y devuelve lista de errores/warnings.

        Prefijo 'WARNING: ' para advertencias; sin prefijo para errores.
        """
        issues: list[str] = []

        # IDs duplicados
        seen_ids: set[str] = set()
        for at in self.assumptions:
            if at.at_id in seen_ids:
                issues.append(f"ID duplicado: {at.at_id!r}")
            seen_ids.add(at.at_id)

        # Multiples ATs activas resolviendo el mismo CONT/GAP
        active_resolving: dict[str, list[str]] = {}
        for at in self.assumptions:
            if at.is_active() and at.resolves_ref:
                active_resolving.setdefault(at.resolves_ref, []).append(at.at_id)
        for ref, ids in active_resolving.items():
            if len(ids) > 1:
                issues.append(
                    f"Multiples AT activas resuelven {ref!r}: {ids}. "
                    "Solo una AT activa puede resolver el mismo CONT/GAP."
                )

        # Validar cada AT individual
        for at in self.assumptions:
            for err in at.validate():
                issues.append(f"{at.at_id}: {err}")

        # Warning: RESUELTA sin nota de resolucion
        for at in self.assumptions:
            if at.status == "RESUELTA" and not at.notes:
                issues.append(
                    f"WARNING: {at.at_id} tiene status RESUELTA "
                    "pero sin nota de resolucion"
                )

        return issues

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "assumptions": [a.to_dict() for a in self.assumptions],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        active = self.active_assumptions()
        resolved = self.resolved_assumptions()
        blocks = self.blocks_administrative_submission()

        lines = [
            "--- OB-05 Sistema AT (Asunciones de Test) ---",
            f"Expediente     : {self.expediente_id}",
            f"Total ATs      : {len(self.assumptions)}",
            f"Activas        : {len(active)}",
            f"Resueltas/desc.: {len(resolved)}",
            f"Bloquea aptitud: {'SI' if blocks else 'NO'}",
        ]
        if active:
            lines.append("")
            lines.append("Asunciones activas:")
            for at in active:
                lines.append(f"  {at.summary()}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Funciones de creacion
# ---------------------------------------------------------------------------


def create_assumption_from_gap(
    at_id: str,
    gap_id: str,
    description: str,
    scope: str,
    severity: str = "ALTA",
    justification: str = "",
    affected_phases: list[str] | None = None,
) -> AsuncionTest:
    """Crea una AT vinculada a un GAP existente.

    La AT queda ACTIVA con impide_aptitud_administrativa=True.
    No confirma datos ni resuelve el gap.
    """
    return AsuncionTest(
        at_id=at_id,
        title=f"Asuncion provisional para {gap_id}",
        description=description,
        resolves_ref=gap_id,
        linked_refs=[gap_id],
        scope=scope,
        severity=severity,
        status="ACTIVA",
        justification=justification,
        affected_phases=list(affected_phases) if affected_phases else [],
        affected_outputs=[],
        impide_aptitud_administrativa=True,
        created_from="create_assumption_from_gap",
        notes=[],
        warnings=[],
    )


def create_assumption_from_cont(
    at_id: str,
    cont_id: str,
    description: str,
    scope: str,
    severity: str = "ALTA",
    justification: str = "",
    affected_phases: list[str] | None = None,
) -> AsuncionTest:
    """Crea una AT vinculada a una contradiccion (CONT) existente.

    La AT queda ACTIVA con impide_aptitud_administrativa=True.
    No confirma datos ni resuelve la contradiccion.
    """
    return AsuncionTest(
        at_id=at_id,
        title=f"Asuncion provisional para {cont_id}",
        description=description,
        resolves_ref=cont_id,
        linked_refs=[cont_id],
        scope=scope,
        severity=severity,
        status="ACTIVA",
        justification=justification,
        affected_phases=list(affected_phases) if affected_phases else [],
        affected_outputs=[],
        impide_aptitud_administrativa=True,
        created_from="create_assumption_from_cont",
        notes=[],
        warnings=[],
    )


# ---------------------------------------------------------------------------
# Carga y escritura
# ---------------------------------------------------------------------------


def load_assumptions_registry(path: str | Path) -> AsuncionTestRegistry:
    """Carga el registro de ATs desde asunciones_test.json.

    Si el archivo no existe, devuelve un registro vacio.
    Si el JSON es invalido, lanza ValueError.
    """
    p = Path(path)
    if not p.exists():
        # Intentar inferir el expediente_id desde la ruta
        # Patron esperado: .../expediente-EIA-XXX/control_interno/asunciones_test.json
        try:
            expediente_id = p.parent.parent.name or "UNKNOWN"
        except Exception:
            expediente_id = "UNKNOWN"
        return AsuncionTestRegistry(expediente_id=expediente_id)

    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"No se pudo leer {p}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON corrupto en {p}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"JSON raiz debe ser un objeto en {p}")

    assumptions: list[AsuncionTest] = []
    for item in data.get("assumptions", []):
        if not isinstance(item, dict):
            raise ValueError(f"Cada assumption debe ser un objeto en {p}")
        try:
            at = AsuncionTest(
                at_id=item["at_id"],
                title=item["title"],
                description=item["description"],
                resolves_ref=item.get("resolves_ref"),
                linked_refs=list(item.get("linked_refs", [])),
                scope=item["scope"],
                severity=item["severity"],
                status=item["status"],
                justification=item.get("justification", ""),
                affected_phases=list(item.get("affected_phases", [])),
                affected_outputs=list(item.get("affected_outputs", [])),
                impide_aptitud_administrativa=item.get(
                    "impide_aptitud_administrativa", True
                ),
                created_from=item.get("created_from", ""),
                notes=list(item.get("notes", [])),
                warnings=list(item.get("warnings", [])),
            )
        except KeyError as exc:
            raise ValueError(
                f"Campo obligatorio faltante en assumption: {exc}"
            ) from exc
        assumptions.append(at)

    return AsuncionTestRegistry(
        expediente_id=data.get("expediente_id", "UNKNOWN"),
        assumptions=assumptions,
        warnings=list(data.get("warnings", [])),
        notes=list(data.get("notes", [])),
    )


def write_assumptions_registry(
    registry: AsuncionTestRegistry,
    output_path: str | Path,
) -> Path:
    """Escribe el registro de ATs en JSON UTF-8 indentado.

    Devuelve la ruta del archivo escrito.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(registry.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# Extraccion de referencias
# ---------------------------------------------------------------------------


def extract_active_assumption_refs(
    registry: AsuncionTestRegistry,
) -> list[str]:
    """Devuelve lista deduplicada de referencias activas: AT-NNN, CONT-NNN, GAP-NNN, etc.

    Incluye at_id, resolves_ref y linked_refs de cada AT activa.
    No incluye referencias de ATs resueltas o descartadas.
    """
    refs: list[str] = []
    seen: set[str] = set()

    def _add(ref: str) -> None:
        if ref and ref not in seen:
            refs.append(ref)
            seen.add(ref)

    for at in registry.active_assumptions():
        _add(at.at_id)
        if at.resolves_ref:
            _add(at.resolves_ref)
        for ref in at.linked_refs:
            _add(ref)

    return refs


# ---------------------------------------------------------------------------
# Generacion de markdown
# ---------------------------------------------------------------------------


def build_assumptions_markdown(registry: AsuncionTestRegistry) -> str:
    """Genera informe markdown del registro de ATs."""
    active = registry.active_assumptions()
    resolved = registry.resolved_assumptions()
    blocks = registry.blocks_administrative_submission()
    refs = extract_active_assumption_refs(registry)

    lines: list[str] = [
        "# Asunciones de test activas",
        "",
        "## 1. Resumen",
        "",
        f"- Expediente: `{registry.expediente_id}`",
        f"- Total asunciones registradas: {len(registry.assumptions)}",
        f"- Asunciones activas: {len(active)}",
        f"- Asunciones resueltas/descartadas: {len(resolved)}",
        f"- Bloquea aptitud administrativa: {'**SI**' if blocks else 'NO'}",
        "",
        "## 2. Asunciones activas",
        "",
    ]

    if not active:
        lines.append("_Sin asunciones activas._")
    else:
        for at in active:
            lines += [
                f"### {at.at_id} — {at.title}",
                "",
                f"- **Scope**: {at.scope}",
                f"- **Severidad**: {at.severity}",
                f"- **Referencia resuelta**: {at.resolves_ref or '—'}",
                f"- **Descripcion**: {at.description}",
                f"- **Justificacion**: {at.justification or '—'}",
                f"- **Fases afectadas**: {', '.join(at.affected_phases) or '—'}",
                "",
            ]

    lines += [
        "## 3. Asunciones resueltas/descartadas",
        "",
    ]

    if not resolved:
        lines.append("_Sin asunciones resueltas o descartadas._")
    else:
        for at in resolved:
            lines.append(f"- **{at.at_id}** ({at.status}): {at.title}")

    lines += [
        "",
        "## 4. Efecto sobre aptitud administrativa",
        "",
        (
            "Mientras existan asunciones de test activas, el expediente no debe "
            "considerarse apto para presentacion administrativa."
        ),
        "",
        "**Estado actual**: "
        + (
            "El expediente tiene asunciones activas. NO APTO para presentacion."
            if blocks
            else "No hay asunciones activas. Sin efecto bloqueante por ATs."
        ),
        "",
        "## 5. Referencias afectadas",
        "",
    ]

    if refs:
        for ref in refs:
            lines.append(f"- `{ref}`")
    else:
        lines.append("_Sin referencias afectadas._")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Integracion con auditoria
# ---------------------------------------------------------------------------


def assumptions_block_administrative_submission(
    expediente_path: str | Path,
) -> bool:
    """Comprueba si existen ATs activas que bloqueen la aptitud administrativa.

    Busca control_interno/asunciones_test.json en el expediente.
    Devuelve False si el archivo no existe o no hay ATs activas.
    Devuelve False (con tolerancia) si el JSON es invalido.
    """
    p = Path(expediente_path)
    at_json = p / "control_interno" / "asunciones_test.json"

    if not at_json.exists():
        return False

    try:
        registry = load_assumptions_registry(at_json)
    except ValueError:
        return False

    return registry.blocks_administrative_submission()
