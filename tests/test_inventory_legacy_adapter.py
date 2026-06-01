"""
Tests para compatibilidad de inventarios AG-08 historicos.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.inventory_builder import build_inventory_from_phase4
from eia_agent.core.inventory_legacy_adapter import adapt_legacy_inventory_index
from eia_agent.core.phase5_gate import evaluate_phase5_gate


def _write_legacy_index(exp: Path) -> Path:
    fichas = exp / "fichas_inventario"
    fichas.mkdir(parents=True)
    items = []
    for i in range(1, 17):
        factor_id = f"FI-{i:03d}"
        item = {
            "id": factor_id,
            "factor": f"Factor {factor_id}",
            "archivo": f"fichas_inventario/{factor_id}.md",
            "estado_evidencia": "CONFIRMADO_GABINETE",
            "semaforo": "VERDE",
            "apto_ag09": True,
            "precaucion_ag09": "Caracterizacion suficiente en gabinete.",
            "hc_base": [f"HC-{i:03d}"],
            "cautelas": [],
        }
        items.append(item)

    items[13].update({
        "id": "FI-014",
        "factor": "Ruido",
        "estado_evidencia": "DECLARADO",
        "semaforo": "ROJO",
        "apto_ag09": True,
        "precaucion_ag09": "Sin estudio acustico de propagacion.",
        "gaps_bloqueantes": ["GAP-RUIDO-001"],
    })

    index = fichas / "indice_inventario.json"
    index.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


class TestInventoryLegacyAdapter(unittest.TestCase):

    def test_adapts_legacy_index_to_16_factors(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-LEGACY"
            exp.mkdir()
            _write_legacy_index(exp)

            result = adapt_legacy_inventory_index(exp)

            self.assertEqual(result.adapted_count, 16)
            self.assertEqual(result.inventory_summary.total_factors, 16)
            self.assertFalse(result.inventory_summary.all_ready_for_phase6)

    def test_preserves_alta_gap_and_blocks_ready_elevation(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-LEGACY"
            exp.mkdir()
            _write_legacy_index(exp)

            result = adapt_legacy_inventory_index(exp)
            fi014 = next(f for f in result.inventory_summary.factors if f.factor_id == "FI-014")

            self.assertEqual(fi014.inventory_semaphore, "ROJO")
            self.assertFalse(fi014.ready_for_impact_assessment)
            self.assertEqual(fi014.gaps[0].criticality, "ALTA")

    def test_write_outputs_creates_inventory_summary_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-LEGACY"
            exp.mkdir()
            _write_legacy_index(exp)

            adapt_legacy_inventory_index(exp, write_outputs=True)
            out = exp / "inventario" / "inventory_summary.json"

            self.assertTrue(out.exists())
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(data["factors"]), 16)

    def test_phase5_gate_flags_legacy_rojo_as_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-LEGACY"
            exp.mkdir()
            _write_legacy_index(exp)

            result = adapt_legacy_inventory_index(exp)
            gate = evaluate_phase5_gate(result.inventory_summary)

            self.assertEqual(gate.decision, "APTO_FASE6_CON_CAUTELAS")
            self.assertIn("FI-014", gate.not_ready_factors)
            self.assertEqual(len(gate.critical_gaps), 1)

    def test_inventory_build_falls_back_to_legacy_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-LEGACY"
            exp.mkdir()
            _write_legacy_index(exp)

            result = build_inventory_from_phase4(exp, write_outputs=True)

            self.assertEqual(result.factor_count, 16)
            self.assertTrue((exp / "inventario" / "inventory_summary.json").exists())
            self.assertTrue(any("Compatibilidad legacy" in n for n in result.notes))


if __name__ == "__main__":
    unittest.main()

