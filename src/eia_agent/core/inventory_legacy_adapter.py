"""
inventory_legacy_adapter -- compatibilidad con inventarios AG-08 historicos.

Convierte `fichas_inventario/indice_inventario.json` (pilotos y expedientes
avanzados anteriores al pipeline IV-02) en el modelo productizado
`inventario/inventory_summary.json`.

Principios:
  - No eleva evidencia.
  - No cierra gaps.
  - No declara aptitud administrativa.
  - Conserva cautelas, pendientes y bloqueos como warnings/notas/gaps.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eia_agent.core.inventory_model import (
    FACTOR_NAMES,
    FactorInventory,
    InventoryGap,
    InventorySummary,
    build_empty_factor_inventory,
    build_inventory_summary,
)


LEGACY_INDEX_RELATIVE_PATH = "fichas_inventario/indice_inventario.json"
ADAPTED_SUMMARY_RELATIVE_PATH = "inventario/inventory_summary.json"

_VALID_EVIDENCE = {
    "CONFIRMADO_CAMPO",
    "CONFIRMADO_GABINETE",
    "CONFIRMADO",
    "DECLARADO",
    "ASUNCION_TEST",
    "INFERIDO_TECNICO",
    "INFERIDO",
    "LIMITADO_ESCALA",
    "ESTIMADO",
    "PROVISIONAL",
    "PENDIENTE_VERIFICACION",
    "PENDIENTE",
    "NO_CONSTA",
    "DESCARTADO",
    "ERROR",
}

_VALID_SEMAPHORES = {
    "VERDE",
    "VERDE_AMARILLO",
    "AMARILLO",
    "ROJO_AMARILLO",
    "ROJO",
    "NO_CONSTA",
}


@dataclass
class LegacyInventoryAdaptResult:
    """Resultado de adaptar un indice AG-08 historico."""

    expediente_id: str
    inventory_summary: InventorySummary
    source_path: str
    output_path: str | None = None
    adapted_count: int = 0
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "adapted_count": self.adapted_count,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "inventory_summary": self.inventory_summary.to_dict(),
            "administrative_ready": False,
        }

    def summary(self) -> str:
        return (
            f"Inventario legacy adaptado -- {self.expediente_id}: "
            f"{self.adapted_count}/16 factores"
        )


def _load_legacy_index(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Indice legacy no encontrado: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("indice_inventario.json debe contener una lista de factores.")
    return [item for item in data if isinstance(item, dict)]


def _clean_evidence(value: Any) -> str:
    text = str(value or "PENDIENTE").strip().upper().replace("-", "_").replace(" ", "_")
    return text if text in _VALID_EVIDENCE else "PENDIENTE"


def _clean_semaphore(value: Any) -> str:
    text = str(value or "NO_CONSTA").strip().upper().replace("-", "_").replace(" ", "_")
    return text if text in _VALID_SEMAPHORES else "NO_CONSTA"


def _legacy_ready(value: Any, semaphore: str, has_alta_gap: bool) -> bool:
    if value is True:
        return semaphore not in {"ROJO", "NO_CONSTA"} and not has_alta_gap
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "si", "sí", "apto", "con cautela"}:
            return semaphore not in {"ROJO", "NO_CONSTA"} and not has_alta_gap
    return False


def _field_mode(item: dict[str, Any], semaphore: str, evidence_status: str) -> str:
    if evidence_status == "NO_CONSTA":
        return "NO_CONSTA"
    if semaphore == "ROJO":
        return "CAMPO_NECESARIO"
    if item.get("gaps_bloqueantes") or item.get("pendientes") or item.get("cautelas"):
        return "CAMPO_RECOMENDADO"
    return "GABINETE_SUFICIENTE"


def _gap(
    gap_id: str,
    factor_id: str,
    description: str,
    criticality: str,
    resolution_mode: str,
) -> InventoryGap:
    return InventoryGap(
        gap_id=gap_id,
        factor_id=factor_id,
        field="inventario_legacy",
        description=description,
        criticality=criticality,
        resolution_mode=resolution_mode,
        status="PENDIENTE",
    )


def _legacy_gaps(item: dict[str, Any], factor_id: str) -> list[InventoryGap]:
    gaps: list[InventoryGap] = []

    for raw in item.get("gaps_bloqueantes") or []:
        gap_id = str(raw)
        gaps.append(_gap(
            gap_id=gap_id,
            factor_id=factor_id,
            description=f"Gap bloqueante heredado de AG-08: {gap_id}.",
            criticality="ALTA",
            resolution_mode="CAMPO",
        ))

    for idx, raw in enumerate(item.get("pendientes") or [], 1):
        desc = str(raw)
        gaps.append(_gap(
            gap_id=f"GAP-{factor_id}-PEND-{idx:03d}",
            factor_id=factor_id,
            description=desc,
            criticality="MEDIA",
            resolution_mode="GABINETE",
        ))

    return gaps


def _factor_from_legacy_item(item: dict[str, Any]) -> FactorInventory | None:
    factor_id = str(item.get("id") or item.get("factor_id") or "").strip()
    if factor_id not in FACTOR_NAMES:
        return None

    evidence_status = _clean_evidence(item.get("estado_evidencia"))
    semaphore = _clean_semaphore(item.get("semaforo"))
    gaps = _legacy_gaps(item, factor_id)
    has_alta_gap = any(g.criticality == "ALTA" and g.status == "PENDIENTE" for g in gaps)
    ready = _legacy_ready(item.get("apto_ag09"), semaphore, has_alta_gap)

    data_sources: list[str] = []
    archivo = item.get("archivo")
    if archivo:
        data_sources.append(str(archivo))
    for hc in item.get("hc_base") or []:
        data_sources.append(str(hc))

    cautelas = [str(c) for c in item.get("cautelas") or []]
    warnings: list[str] = []
    if cautelas:
        warnings.append(f"Cautelas activas heredadas: {', '.join(cautelas)}")
    if item.get("nota_test"):
        warnings.append(str(item["nota_test"]))

    notes = [
        "Factor adaptado desde fichas_inventario/indice_inventario.json.",
        "Adaptacion de compatibilidad: no eleva evidencia ni resuelve gaps.",
    ]
    if item.get("normativa"):
        notes.append(f"Normativa asociada: {', '.join(str(n) for n in item['normativa'])}")

    description = str(item.get("precaucion_ag09") or item.get("factor") or FACTOR_NAMES[factor_id])
    field_mode = _field_mode(item, semaphore, evidence_status)

    return FactorInventory(
        factor_id=factor_id,
        factor_name=str(item.get("factor") or FACTOR_NAMES[factor_id]),
        description=description,
        data_sources=data_sources,
        evidence_status=evidence_status,
        field_mode=field_mode,
        field_mode_justification="Inferido por adaptador legacy desde semaforo, gaps y cautelas AG-08.",
        inventory_semaphore=semaphore,
        semaphore_justification="Semaforo heredado de fichas_inventario/indice_inventario.json.",
        gaps=gaps,
        ready_for_impact_assessment=ready,
        warnings=warnings,
        notes=notes,
    )


def adapt_legacy_inventory_index(
    expediente_path: str | Path,
    legacy_index_path: str | Path | None = None,
    write_outputs: bool = False,
) -> LegacyInventoryAdaptResult:
    """Adapta el indice de fichas AG-08 al InventorySummary productizado."""
    exp = Path(expediente_path)
    index_path = Path(legacy_index_path) if legacy_index_path else exp / LEGACY_INDEX_RELATIVE_PATH
    items = _load_legacy_index(index_path)

    by_id: dict[str, FactorInventory] = {}
    warnings: list[str] = []
    notes: list[str] = [
        "Inventario reconstruido desde indice AG-08 historico.",
        "No apto administrativamente por si solo; requiere auditoria M-12.",
    ]

    for item in items:
        factor = _factor_from_legacy_item(item)
        if factor is None:
            warnings.append(f"Item legacy ignorado por factor_id no canonico: {item.get('id')!r}")
            continue
        by_id[factor.factor_id] = factor

    factors: list[FactorInventory] = []
    for factor_id in sorted(FACTOR_NAMES.keys()):
        factors.append(by_id.get(factor_id) or build_empty_factor_inventory(factor_id))

    summary = build_inventory_summary(exp.name, factors)
    summary.warnings.extend(warnings)
    summary.notes.extend(notes)

    output_path: str | None = None
    if write_outputs:
        out_dir = exp / "inventario"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "inventory_summary.json"
        out.write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        output_path = str(out)

    return LegacyInventoryAdaptResult(
        expediente_id=exp.name,
        inventory_summary=summary,
        source_path=str(index_path),
        output_path=output_path,
        adapted_count=len(by_id),
        warnings=warnings,
        notes=notes,
    )

