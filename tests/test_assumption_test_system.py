"""
Tests para assumption_test_system -- OB-05
Sistema AT (Asunciones de Test) para EIA-Agent v2.1.

Usa unittest puro. Sin pytest, sin web, sin IA, sin llamadas externas.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.assumption_test_system import (
    ASSUMPTION_SCOPE,
    ASSUMPTION_SEVERITY,
    ASSUMPTION_STATUS,
    AsuncionTest,
    AsuncionTestRegistry,
    assumptions_block_administrative_submission,
    build_assumptions_markdown,
    create_assumption_from_cont,
    create_assumption_from_gap,
    extract_active_assumption_refs,
    load_assumptions_registry,
    write_assumptions_registry,
)


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------


def _make_at(
    at_id: str = "AT-001",
    title: str = "Titulo de prueba",
    description: str = "Descripcion de prueba",
    scope: str = "INVENTARIO",
    severity: str = "ALTA",
    status: str = "ACTIVA",
    justification: str = "Justificacion de prueba",
    impide: bool = True,
    resolves_ref: str | None = None,
    linked_refs: list | None = None,
    notes: list | None = None,
) -> AsuncionTest:
    return AsuncionTest(
        at_id=at_id,
        title=title,
        description=description,
        scope=scope,
        severity=severity,
        status=status,
        justification=justification,
        impide_aptitud_administrativa=impide,
        resolves_ref=resolves_ref,
        linked_refs=linked_refs or [],
        notes=notes or [],
    )


def _make_registry(assumptions: list[AsuncionTest] | None = None) -> AsuncionTestRegistry:
    return AsuncionTestRegistry(
        expediente_id="EIA-2026-TEST",
        assumptions=assumptions or [],
    )


# ---------------------------------------------------------------------------
# 1. AsuncionTest
# ---------------------------------------------------------------------------


class TestAsuncionTestCreacionValida(unittest.TestCase):
    def setUp(self):
        self.at = _make_at()

    def test_campos_basicos(self):
        self.assertEqual(self.at.at_id, "AT-001")
        self.assertEqual(self.at.scope, "INVENTARIO")
        self.assertEqual(self.at.status, "ACTIVA")
        self.assertTrue(self.at.impide_aptitud_administrativa)

    def test_validate_vacio(self):
        self.assertEqual(self.at.validate(), [])

    def test_is_active_true(self):
        self.assertTrue(self.at.is_active())

    def test_to_dict_tiene_campos_requeridos(self):
        d = self.at.to_dict()
        for campo in (
            "at_id", "title", "description", "resolves_ref", "linked_refs",
            "scope", "severity", "status", "justification",
            "affected_phases", "affected_outputs",
            "impide_aptitud_administrativa", "created_from", "notes", "warnings",
        ):
            self.assertIn(campo, d)

    def test_to_dict_serializable_json(self):
        d = self.at.to_dict()
        s = json.dumps(d)
        self.assertIsInstance(s, str)

    def test_summary_contiene_at_id(self):
        s = self.at.summary()
        self.assertIn("AT-001", s)

    def test_summary_contiene_status(self):
        self.assertIn("ACTIVA", self.at.summary())


class TestAsuncionTestAtIdInvalido(unittest.TestCase):
    def _check(self, at_id: str, should_fail: bool = True):
        at = _make_at(at_id=at_id)
        errors = at.validate()
        if should_fail:
            self.assertTrue(
                any("at_id" in e for e in errors),
                f"Esperaba error de at_id para {at_id!r}, errors={errors}",
            )
        else:
            self.assertFalse(any("at_id" in e for e in errors))

    def test_sin_guion(self):
        self._check("AT001")

    def test_sin_prefix(self):
        self._check("001")

    def test_prefix_minuscula(self):
        self._check("at-001")

    def test_solo_dos_digitos(self):
        self._check("AT-01")

    def test_tres_digitos_ok(self):
        self._check("AT-001", should_fail=False)

    def test_cuatro_digitos_ok(self):
        self._check("AT-0001", should_fail=False)

    def test_vacio(self):
        self._check("")


class TestAsuncionTestScopeInvalido(unittest.TestCase):
    def test_scope_invalido(self):
        at = _make_at(scope="INVALIDO")
        errors = at.validate()
        self.assertTrue(any("scope" in e for e in errors))

    def test_scope_vacio(self):
        at = _make_at(scope="")
        errors = at.validate()
        self.assertTrue(any("scope" in e for e in errors))

    def test_scope_validos(self):
        for scope in ASSUMPTION_SCOPE:
            at = _make_at(scope=scope)
            errors = at.validate()
            self.assertFalse(
                any("scope" in e for e in errors),
                f"scope {scope!r} no deberia dar error",
            )


class TestAsuncionTestSeverityInvalida(unittest.TestCase):
    def test_severity_invalida(self):
        at = _make_at(severity="CRITICA")
        errors = at.validate()
        self.assertTrue(any("severity" in e for e in errors))

    def test_severity_validas(self):
        for sev in ASSUMPTION_SEVERITY:
            at = _make_at(severity=sev)
            errors = at.validate()
            self.assertFalse(
                any("severity" in e for e in errors),
                f"severity {sev!r} no deberia dar error",
            )


class TestAsuncionTestStatusInvalido(unittest.TestCase):
    def test_status_invalido(self):
        at = _make_at(status="PENDIENTE")
        errors = at.validate()
        self.assertTrue(any("status" in e for e in errors))

    def test_status_validos(self):
        for st in ASSUMPTION_STATUS:
            justif = "ok" if st == "ACTIVA" else ""
            at = _make_at(status=st, justification=justif)
            errors = [e for e in at.validate() if "status" in e]
            self.assertFalse(errors, f"status {st!r} no deberia dar error de status")


class TestAsuncionTestImpideAdmin(unittest.TestCase):
    def test_activa_false_impide_falla(self):
        at = _make_at(status="ACTIVA", impide=False)
        errors = at.validate()
        self.assertTrue(any("impide_aptitud_administrativa" in e for e in errors))

    def test_resuelta_false_impide_ok(self):
        at = _make_at(status="RESUELTA", impide=False, justification="")
        errors = [e for e in at.validate() if "impide_aptitud_administrativa" in e]
        self.assertFalse(errors)

    def test_descartada_false_impide_ok(self):
        at = _make_at(status="DESCARTADA", impide=False, justification="")
        errors = [e for e in at.validate() if "impide_aptitud_administrativa" in e]
        self.assertFalse(errors)


class TestAsuncionTestBlocksAdmin(unittest.TestCase):
    def test_activa_bloquea(self):
        at = _make_at(status="ACTIVA")
        self.assertTrue(at.blocks_administrative_submission())

    def test_resuelta_no_bloquea(self):
        at = _make_at(status="RESUELTA", justification="")
        self.assertFalse(at.blocks_administrative_submission())

    def test_descartada_no_bloquea(self):
        at = _make_at(status="DESCARTADA", justification="")
        self.assertFalse(at.blocks_administrative_submission())

    def test_sustituida_no_bloquea(self):
        at = _make_at(status="SUSTITUIDA", justification="")
        self.assertFalse(at.blocks_administrative_submission())

    def test_activa_impide_false_no_bloquea(self):
        # impide=False en AT activa es incoherente pero el metodo es descriptivo
        at = _make_at(status="ACTIVA", impide=False)
        self.assertFalse(at.blocks_administrative_submission())


class TestAsuncionTestJustificationRequerida(unittest.TestCase):
    def test_activa_sin_justification_falla(self):
        at = _make_at(status="ACTIVA", justification="")
        errors = at.validate()
        self.assertTrue(any("justification" in e for e in errors))

    def test_resuelta_sin_justification_ok(self):
        at = _make_at(status="RESUELTA", justification="")
        errors = [e for e in at.validate() if "justification" in e]
        self.assertFalse(errors)


# ---------------------------------------------------------------------------
# 2. AsuncionTestRegistry
# ---------------------------------------------------------------------------


class TestAsuncionTestRegistryActivasResueltas(unittest.TestCase):
    def setUp(self):
        self.activa = _make_at(at_id="AT-001", status="ACTIVA")
        self.resuelta = _make_at(at_id="AT-002", status="RESUELTA", justification="")
        self.descartada = _make_at(at_id="AT-003", status="DESCARTADA", justification="")
        self.sustituida = _make_at(at_id="AT-004", status="SUSTITUIDA", justification="")
        self.registry = _make_registry(
            [self.activa, self.resuelta, self.descartada, self.sustituida]
        )

    def test_active_assumptions(self):
        activas = self.registry.active_assumptions()
        self.assertEqual(len(activas), 1)
        self.assertEqual(activas[0].at_id, "AT-001")

    def test_resolved_assumptions(self):
        resueltas = self.registry.resolved_assumptions()
        self.assertEqual(len(resueltas), 3)
        ids = {a.at_id for a in resueltas}
        self.assertIn("AT-002", ids)
        self.assertIn("AT-003", ids)
        self.assertIn("AT-004", ids)


class TestAsuncionTestRegistryBlocksAdmin(unittest.TestCase):
    def test_sin_activas_no_bloquea(self):
        at = _make_at(at_id="AT-001", status="RESUELTA", justification="")
        registry = _make_registry([at])
        self.assertFalse(registry.blocks_administrative_submission())

    def test_con_activa_bloquea(self):
        at = _make_at(at_id="AT-001", status="ACTIVA")
        registry = _make_registry([at])
        self.assertTrue(registry.blocks_administrative_submission())

    def test_vacio_no_bloquea(self):
        registry = _make_registry([])
        self.assertFalse(registry.blocks_administrative_submission())


class TestAsuncionTestRegistryByScope(unittest.TestCase):
    def setUp(self):
        self.at1 = _make_at(at_id="AT-001", scope="INVENTARIO")
        self.at2 = _make_at(at_id="AT-002", scope="IMPACTO")
        self.at3 = _make_at(at_id="AT-003", scope="INVENTARIO")
        self.registry = _make_registry([self.at1, self.at2, self.at3])

    def test_by_scope_inventario(self):
        result = self.registry.by_scope("INVENTARIO")
        self.assertEqual(len(result), 2)

    def test_by_scope_impacto(self):
        result = self.registry.by_scope("IMPACTO")
        self.assertEqual(len(result), 1)

    def test_by_scope_inexistente(self):
        result = self.registry.by_scope("PVA")
        self.assertEqual(len(result), 0)


class TestAsuncionTestRegistryByRef(unittest.TestCase):
    def setUp(self):
        self.at1 = _make_at(
            at_id="AT-001", resolves_ref="GAP-001", linked_refs=["GAP-001", "CONT-002"]
        )
        self.at2 = _make_at(at_id="AT-002", linked_refs=["IMP-003"])
        self.registry = _make_registry([self.at1, self.at2])

    def test_by_ref_resolves_ref(self):
        result = self.registry.by_ref("GAP-001")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].at_id, "AT-001")

    def test_by_ref_linked_refs(self):
        result = self.registry.by_ref("CONT-002")
        self.assertEqual(len(result), 1)

    def test_by_ref_otro(self):
        result = self.registry.by_ref("IMP-003")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].at_id, "AT-002")

    def test_by_ref_no_encontrado(self):
        result = self.registry.by_ref("GAP-999")
        self.assertEqual(len(result), 0)


class TestAsuncionTestRegistryValidate(unittest.TestCase):
    def test_ids_duplicados_error(self):
        at1 = _make_at(at_id="AT-001")
        at2 = _make_at(at_id="AT-001")
        registry = _make_registry([at1, at2])
        issues = registry.validate()
        self.assertTrue(any("duplicado" in i for i in issues))

    def test_dos_activas_mismo_cont_error(self):
        at1 = _make_at(at_id="AT-001", resolves_ref="CONT-001")
        at2 = _make_at(at_id="AT-002", resolves_ref="CONT-001")
        registry = _make_registry([at1, at2])
        issues = registry.validate()
        self.assertTrue(
            any("CONT-001" in i for i in issues),
            f"Esperaba error de CONT-001 duplicado, issues={issues}",
        )

    def test_dos_activas_mismo_gap_error(self):
        at1 = _make_at(at_id="AT-001", resolves_ref="GAP-005")
        at2 = _make_at(at_id="AT-002", resolves_ref="GAP-005")
        registry = _make_registry([at1, at2])
        issues = registry.validate()
        self.assertTrue(any("GAP-005" in i for i in issues))

    def test_registry_valido_sin_errores(self):
        at = _make_at(at_id="AT-001")
        registry = _make_registry([at])
        issues = registry.validate()
        # No debe haber errores (puede haber warnings prefijados con WARNING:)
        errores = [i for i in issues if not i.startswith("WARNING:")]
        self.assertEqual(errores, [])

    def test_resuelta_sin_nota_warning(self):
        at = _make_at(at_id="AT-001", status="RESUELTA", justification="", notes=[])
        registry = _make_registry([at])
        issues = registry.validate()
        self.assertTrue(any("WARNING:" in i and "RESUELTA" in i for i in issues))

    def test_at_invalida_propaga_error(self):
        at = _make_at(at_id="AT-001", scope="INVALIDO")
        registry = _make_registry([at])
        issues = registry.validate()
        self.assertTrue(any("scope" in i for i in issues))

    def test_summary_contiene_expediente_id(self):
        registry = _make_registry([_make_at()])
        s = registry.summary()
        self.assertIn("EIA-2026-TEST", s)

    def test_summary_contiene_contador(self):
        registry = _make_registry([_make_at()])
        s = registry.summary()
        self.assertIn("1", s)


# ---------------------------------------------------------------------------
# 3. create_assumption_from_gap
# ---------------------------------------------------------------------------


class TestCreateAssumptionFromGap(unittest.TestCase):
    def setUp(self):
        self.at = create_assumption_from_gap(
            at_id="AT-001",
            gap_id="GAP-FI-001-001",
            description="Datos climaticos no disponibles en modo gabinete",
            scope="INVENTARIO",
            severity="ALTA",
            justification="Se asume clima Koppen BWh segun datos AEMET historicos",
            affected_phases=["5", "6"],
        )

    def test_crea_at_activa(self):
        self.assertEqual(self.at.status, "ACTIVA")

    def test_resolves_ref_es_gap(self):
        self.assertEqual(self.at.resolves_ref, "GAP-FI-001-001")

    def test_bloquea_aptitud_administrativa(self):
        self.assertTrue(self.at.blocks_administrative_submission())

    def test_impide_aptitud_administrativa_true(self):
        self.assertTrue(self.at.impide_aptitud_administrativa)

    def test_at_id_correcto(self):
        self.assertEqual(self.at.at_id, "AT-001")

    def test_fases_afectadas(self):
        self.assertEqual(self.at.affected_phases, ["5", "6"])

    def test_linked_refs_contiene_gap(self):
        self.assertIn("GAP-FI-001-001", self.at.linked_refs)

    def test_created_from(self):
        self.assertEqual(self.at.created_from, "create_assumption_from_gap")

    def test_validate_valida(self):
        self.assertEqual(self.at.validate(), [])

    def test_sin_fases_afectadas(self):
        at = create_assumption_from_gap(
            at_id="AT-002",
            gap_id="GAP-FI-002-001",
            description="Desc",
            scope="GLOBAL",
            justification="just",
        )
        self.assertEqual(at.affected_phases, [])


# ---------------------------------------------------------------------------
# 4. create_assumption_from_cont
# ---------------------------------------------------------------------------


class TestCreateAssumptionFromCont(unittest.TestCase):
    def setUp(self):
        self.at = create_assumption_from_cont(
            at_id="AT-003",
            cont_id="CONT-001",
            description="Uso catastral agricola vs uso industrial declarado",
            scope="OBJETO",
            severity="ALTA",
            justification="Se asume uso industrial segun licencia municipal",
        )

    def test_crea_at_activa(self):
        self.assertEqual(self.at.status, "ACTIVA")

    def test_resolves_ref_es_cont(self):
        self.assertEqual(self.at.resolves_ref, "CONT-001")

    def test_bloquea_aptitud_administrativa(self):
        self.assertTrue(self.at.blocks_administrative_submission())

    def test_impide_aptitud_administrativa_true(self):
        self.assertTrue(self.at.impide_aptitud_administrativa)

    def test_at_id_correcto(self):
        self.assertEqual(self.at.at_id, "AT-003")

    def test_linked_refs_contiene_cont(self):
        self.assertIn("CONT-001", self.at.linked_refs)

    def test_created_from(self):
        self.assertEqual(self.at.created_from, "create_assumption_from_cont")

    def test_validate_valida(self):
        self.assertEqual(self.at.validate(), [])

    def test_severity_por_defecto_alta(self):
        at = create_assumption_from_cont(
            at_id="AT-004",
            cont_id="CONT-002",
            description="Desc",
            scope="GLOBAL",
            justification="just",
        )
        self.assertEqual(at.severity, "ALTA")


# ---------------------------------------------------------------------------
# 5. load / write
# ---------------------------------------------------------------------------


class TestLoadWriteAssumptions(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_at_json(self, filename: str, data: dict) -> Path:
        p = self.tmp / filename
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def test_write_crea_json(self):
        at = _make_at(at_id="AT-001")
        registry = _make_registry([at])
        out = self.tmp / "asunciones_test.json"
        result = write_assumptions_registry(registry, out)
        self.assertTrue(out.exists())
        self.assertEqual(result, out)

    def test_write_es_json_valido(self):
        at = _make_at(at_id="AT-001")
        registry = _make_registry([at])
        out = self.tmp / "asunciones_test.json"
        write_assumptions_registry(registry, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn("expediente_id", data)
        self.assertIn("assumptions", data)

    def test_load_reconstruye_registry(self):
        at = _make_at(at_id="AT-001", resolves_ref="GAP-001", linked_refs=["GAP-001"])
        registry = _make_registry([at])
        out = self.tmp / "asunciones_test.json"
        write_assumptions_registry(registry, out)

        loaded = load_assumptions_registry(out)
        self.assertEqual(loaded.expediente_id, "EIA-2026-TEST")
        self.assertEqual(len(loaded.assumptions), 1)
        self.assertEqual(loaded.assumptions[0].at_id, "AT-001")
        self.assertEqual(loaded.assumptions[0].resolves_ref, "GAP-001")

    def test_load_preserve_campos(self):
        at = create_assumption_from_gap(
            at_id="AT-001",
            gap_id="GAP-001",
            description="Desc",
            scope="INVENTARIO",
            justification="Just",
            affected_phases=["5"],
        )
        registry = _make_registry([at])
        out = self.tmp / "asunciones_test.json"
        write_assumptions_registry(registry, out)

        loaded = load_assumptions_registry(out)
        lat = loaded.assumptions[0]
        self.assertEqual(lat.scope, "INVENTARIO")
        self.assertEqual(lat.affected_phases, ["5"])
        self.assertTrue(lat.impide_aptitud_administrativa)

    def test_archivo_inexistente_devuelve_vacio(self):
        p = self.tmp / "expediente-EIA-PRUEBA" / "control_interno" / "asunciones_test.json"
        registry = load_assumptions_registry(p)
        self.assertEqual(len(registry.assumptions), 0)

    def test_archivo_inexistente_expediente_id_inferido(self):
        p = self.tmp / "expediente-EIA-PRUEBA" / "control_interno" / "asunciones_test.json"
        registry = load_assumptions_registry(p)
        # El expediente_id debe ser el directorio padre del padre (nombre del expediente)
        self.assertIn("expediente-EIA-PRUEBA", registry.expediente_id)

    def test_json_corrupto_lanza_value_error(self):
        p = self.tmp / "corrupto.json"
        p.write_text("{ esto no es json valido", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_assumptions_registry(p)

    def test_json_no_objeto_lanza_value_error(self):
        p = self.tmp / "lista.json"
        p.write_text("[1, 2, 3]", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_assumptions_registry(p)

    def test_campo_obligatorio_faltante_lanza_value_error(self):
        # AT sin at_id
        data = {
            "expediente_id": "TEST",
            "assumptions": [
                {"title": "T", "description": "D", "scope": "GLOBAL",
                 "severity": "ALTA", "status": "ACTIVA"}
            ]
        }
        p = self.tmp / "faltante.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_assumptions_registry(p)

    def test_write_crea_directorio_padre(self):
        at = _make_at()
        registry = _make_registry([at])
        out = self.tmp / "sub" / "dir" / "asunciones_test.json"
        write_assumptions_registry(registry, out)
        self.assertTrue(out.exists())


# ---------------------------------------------------------------------------
# 6. extract_active_assumption_refs
# ---------------------------------------------------------------------------


class TestExtractActiveAssumptionRefs(unittest.TestCase):
    def test_devuelve_at_y_refs_vinculadas(self):
        at1 = _make_at(at_id="AT-001", resolves_ref="GAP-001", linked_refs=["GAP-001", "IMP-001"])
        at2 = _make_at(at_id="AT-002", resolves_ref="CONT-001", linked_refs=["CONT-001"])
        registry = _make_registry([at1, at2])
        refs = extract_active_assumption_refs(registry)
        self.assertIn("AT-001", refs)
        self.assertIn("AT-002", refs)
        self.assertIn("GAP-001", refs)
        self.assertIn("IMP-001", refs)
        self.assertIn("CONT-001", refs)

    def test_no_incluye_resueltas(self):
        at1 = _make_at(at_id="AT-001", status="ACTIVA", resolves_ref="GAP-001", linked_refs=["GAP-001"])
        at2 = _make_at(at_id="AT-002", status="RESUELTA", resolves_ref="CONT-999", linked_refs=["CONT-999"], justification="")
        registry = _make_registry([at1, at2])
        refs = extract_active_assumption_refs(registry)
        self.assertNotIn("CONT-999", refs)
        self.assertNotIn("AT-002", refs)

    def test_deduplicado(self):
        at1 = _make_at(at_id="AT-001", resolves_ref="GAP-001", linked_refs=["GAP-001"])
        at2 = _make_at(at_id="AT-002", resolves_ref="GAP-001", linked_refs=["GAP-001"])
        # Nota: dos AT con mismo resolves_ref generaria error en validate()
        # pero extract no valida, solo extrae
        registry = _make_registry([at1, at2])
        refs = extract_active_assumption_refs(registry)
        self.assertEqual(refs.count("GAP-001"), 1)

    def test_registro_vacio(self):
        registry = _make_registry([])
        refs = extract_active_assumption_refs(registry)
        self.assertEqual(refs, [])


# ---------------------------------------------------------------------------
# 7. build_assumptions_markdown
# ---------------------------------------------------------------------------


class TestBuildAssumptionsMarkdown(unittest.TestCase):
    def setUp(self):
        self.at = create_assumption_from_gap(
            at_id="AT-001",
            gap_id="GAP-001",
            description="Datos no disponibles",
            scope="INVENTARIO",
            justification="Se asume valor tipico",
        )
        self.registry = _make_registry([self.at])
        self.md = build_assumptions_markdown(self.registry)

    def test_contiene_header(self):
        self.assertIn("# Asunciones de test activas", self.md)

    def test_contiene_asunciones_activas_seccion(self):
        self.assertIn("## 2. Asunciones activas", self.md)

    def test_contiene_at_id(self):
        self.assertIn("AT-001", self.md)

    def test_contiene_advertencia_no_aptitud(self):
        self.assertIn("no debe", self.md)
        self.assertIn("apto para presentacion administrativa", self.md)

    def test_seccion_aptitud_administrativa(self):
        self.assertIn("## 4. Efecto sobre aptitud administrativa", self.md)

    def test_seccion_referencias(self):
        self.assertIn("## 5. Referencias afectadas", self.md)

    def test_contiene_referencia_gap(self):
        self.assertIn("GAP-001", self.md)

    def test_sin_activas_muestra_sin_asunciones(self):
        at_resuelta = _make_at(at_id="AT-001", status="RESUELTA", justification="")
        registry = _make_registry([at_resuelta])
        md = build_assumptions_markdown(registry)
        self.assertIn("Sin asunciones activas", md)

    def test_seccion_resueltas(self):
        self.assertIn("## 3. Asunciones resueltas", self.md)

    def test_expediente_id(self):
        self.assertIn("EIA-2026-TEST", self.md)


# ---------------------------------------------------------------------------
# 8. assumptions_block_administrative_submission
# ---------------------------------------------------------------------------


class TestAssumptionsBlockAdministrativeSubmission(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_exp(self, assumptions: list[AsuncionTest]) -> Path:
        exp = self.tmp / "expediente-EIA-TEST"
        ci = exp / "control_interno"
        ci.mkdir(parents=True)
        registry = AsuncionTestRegistry(
            expediente_id="EIA-TEST",
            assumptions=assumptions,
        )
        write_assumptions_registry(registry, ci / "asunciones_test.json")
        return exp

    def test_sin_archivo_devuelve_false(self):
        exp = self.tmp / "expediente-sin-at"
        exp.mkdir()
        result = assumptions_block_administrative_submission(exp)
        self.assertFalse(result)

    def test_con_at_activa_devuelve_true(self):
        at = _make_at(at_id="AT-001", status="ACTIVA")
        exp = self._make_exp([at])
        result = assumptions_block_administrative_submission(exp)
        self.assertTrue(result)

    def test_con_at_resuelta_devuelve_false(self):
        at = _make_at(at_id="AT-001", status="RESUELTA", justification="")
        exp = self._make_exp([at])
        result = assumptions_block_administrative_submission(exp)
        self.assertFalse(result)

    def test_con_at_descartada_devuelve_false(self):
        at = _make_at(at_id="AT-001", status="DESCARTADA", justification="")
        exp = self._make_exp([at])
        result = assumptions_block_administrative_submission(exp)
        self.assertFalse(result)

    def test_json_corrupto_devuelve_false(self):
        exp = self.tmp / "expediente-corrupto"
        ci = exp / "control_interno"
        ci.mkdir(parents=True)
        (ci / "asunciones_test.json").write_text("{ invalido", encoding="utf-8")
        result = assumptions_block_administrative_submission(exp)
        self.assertFalse(result)

    def test_registro_vacio_devuelve_false(self):
        exp = self._make_exp([])
        result = assumptions_block_administrative_submission(exp)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# 9. CLI — assumptions-summary
# ---------------------------------------------------------------------------


class TestCLIAssumptionsSummary(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_exp(self, assumptions: list[AsuncionTest] | None = None) -> Path:
        exp = self.tmp / "expediente-EIA-CLI"
        ci = exp / "control_interno"
        ci.mkdir(parents=True)
        if assumptions is not None:
            registry = AsuncionTestRegistry(
                expediente_id="EIA-CLI",
                assumptions=assumptions,
            )
            write_assumptions_registry(registry, ci / "asunciones_test.json")
        return exp

    def _run(self, args: list[str]) -> int:
        import sys as _sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import run_expediente
        return run_expediente.main(args)

    def test_sin_archivo_exit_0(self):
        exp = self._make_exp(assumptions=None)
        rc = self._run([str(exp), "assumptions-summary"])
        self.assertEqual(rc, 0)

    def test_con_archivo_valido_sin_write_exit_0(self):
        exp = self._make_exp(assumptions=[_make_at(at_id="AT-001")])
        rc = self._run([str(exp), "assumptions-summary"])
        self.assertEqual(rc, 0)

    def test_con_archivo_valido_no_escribe_md_sin_write(self):
        exp = self._make_exp(assumptions=[_make_at(at_id="AT-001")])
        rc = self._run([str(exp), "assumptions-summary"])
        self.assertEqual(rc, 0)
        md_path = exp / "control_interno" / "asunciones_test_resumen.md"
        self.assertFalse(md_path.exists())

    def test_con_write_crea_md(self):
        exp = self._make_exp(assumptions=[_make_at(at_id="AT-001")])
        rc = self._run([str(exp), "assumptions-summary", "--write"])
        self.assertEqual(rc, 0)
        md_path = exp / "control_interno" / "asunciones_test_resumen.md"
        self.assertTrue(md_path.exists())

    def test_md_contiene_at_id(self):
        exp = self._make_exp(assumptions=[_make_at(at_id="AT-001")])
        self._run([str(exp), "assumptions-summary", "--write"])
        md_path = exp / "control_interno" / "asunciones_test_resumen.md"
        content = md_path.read_text(encoding="utf-8")
        self.assertIn("AT-001", content)

    def test_json_corrupto_exit_1(self):
        exp = self.tmp / "expediente-EIA-CORRUPTO"
        ci = exp / "control_interno"
        ci.mkdir(parents=True)
        (ci / "asunciones_test.json").write_text("{ invalido }", encoding="utf-8")
        rc = self._run([str(exp), "assumptions-summary"])
        self.assertEqual(rc, 1)

    def test_registro_vacio_exit_0(self):
        exp = self._make_exp(assumptions=[])
        rc = self._run([str(exp), "assumptions-summary"])
        self.assertEqual(rc, 0)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------


class TestConstantes(unittest.TestCase):
    def test_assumption_status_tiene_cuatro_valores(self):
        self.assertEqual(len(ASSUMPTION_STATUS), 4)
        self.assertIn("ACTIVA", ASSUMPTION_STATUS)
        self.assertIn("RESUELTA", ASSUMPTION_STATUS)
        self.assertIn("DESCARTADA", ASSUMPTION_STATUS)
        self.assertIn("SUSTITUIDA", ASSUMPTION_STATUS)

    def test_assumption_scope_tiene_once_valores(self):
        self.assertEqual(len(ASSUMPTION_SCOPE), 11)

    def test_assumption_severity_tiene_cuatro_valores(self):
        self.assertEqual(len(ASSUMPTION_SEVERITY), 4)
        self.assertIn("BLOQUEANTE_REAL", ASSUMPTION_SEVERITY)
        self.assertIn("ALTA", ASSUMPTION_SEVERITY)
        self.assertIn("MEDIA", ASSUMPTION_SEVERITY)
        self.assertIn("BAJA", ASSUMPTION_SEVERITY)


if __name__ == "__main__":
    unittest.main()
