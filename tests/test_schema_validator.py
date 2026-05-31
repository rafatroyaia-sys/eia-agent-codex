"""
Tests NL-02 -- schema_validator.py
Ejecutar: venv/Scripts/python -m unittest tests.test_schema_validator
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.schema_validator import (
    ValidationIssue,
    ValidationResult,
    load_schema_index,
    validate_expediente,
    validate_layer,
)

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
PROJECT = Path(__file__).parent.parent.resolve()
SCHEMA_DIR = PROJECT / "config" / "schemas" / "v2_1"
PILOTO_PARCELA = PROJECT / "expediente-EIA-2026-RECIMETAL-PARCELA"
PILOTO_NAVE222 = PROJECT / "expediente-EIA-2026-RECIMETAL-NAVE-222"
_PARCELA_OK = PILOTO_PARCELA.exists()
_NAVE222_OK = PILOTO_NAVE222.exists()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clone_expediente(src: Path) -> Path:
    """Copia un expediente en un directorio temporal. Devuelve la ruta."""
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(src, tmp / src.name)
    return tmp / src.name


# ---------------------------------------------------------------------------
# ValidationIssue
# ---------------------------------------------------------------------------

class TestValidationIssue(unittest.TestCase):

    def test_str_con_code(self):
        issue = ValidationIssue(
            severity="ERROR",
            layer="hechos_confirmados",
            path="[0] / id",
            message="campo requerido ausente",
            code="SCHEMA_VALIDATION_ERROR",
        )
        s = str(issue)
        self.assertIn("ERROR", s)
        self.assertIn("SCHEMA_VALIDATION_ERROR", s)
        self.assertIn("hechos_confirmados", s)

    def test_str_sin_code(self):
        issue = ValidationIssue(
            severity="WARNING",
            layer="normativa_aplicable",
            path="archivo",
            message="algo",
        )
        s = str(issue)
        self.assertIn("WARNING", s)
        self.assertNotIn("None", s)


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

class TestValidationResult(unittest.TestCase):

    def _make_result(self, severities: list) -> ValidationResult:
        result = ValidationResult(
            expediente_path=Path("/tmp/exp"),
            schema_version="2.1",
        )
        for sev in severities:
            result.issues.append(ValidationIssue(
                severity=sev, layer="x", path="x", message="x"
            ))
        return result

    def test_error_count(self):
        r = self._make_result(["ERROR", "ERROR", "WARNING", "INFO"])
        self.assertEqual(r.error_count(), 2)

    def test_warning_count(self):
        r = self._make_result(["ERROR", "WARNING", "WARNING"])
        self.assertEqual(r.warning_count(), 2)

    def test_info_count(self):
        r = self._make_result(["INFO", "INFO", "INFO"])
        self.assertEqual(r.info_count(), 3)

    def test_is_valid_sin_errores(self):
        r = self._make_result(["WARNING", "INFO"])
        self.assertTrue(r.is_valid())

    def test_is_valid_con_errores(self):
        r = self._make_result(["ERROR"])
        self.assertFalse(r.is_valid())

    def test_is_valid_sin_issues(self):
        r = self._make_result([])
        self.assertTrue(r.is_valid())

    def test_summary_contiene_estado(self):
        r = self._make_result([])
        s = r.summary()
        self.assertIn("VALIDO", s)

    def test_summary_no_valido_contiene_no_valido(self):
        r = self._make_result(["ERROR"])
        s = r.summary()
        self.assertIn("NO VALIDO", s)

    def test_summary_contiene_conteos(self):
        r = self._make_result(["ERROR", "WARNING"])
        s = r.summary()
        self.assertIn("1 errores", s)
        self.assertIn("1 avisos", s)

    def test_summary_contiene_ruta_expediente(self):
        r = ValidationResult(
            expediente_path=Path("/ruta/al/expediente"),
            schema_version="2.1",
        )
        s = r.summary()
        self.assertIn("expediente", s.lower())


# ---------------------------------------------------------------------------
# load_schema_index
# ---------------------------------------------------------------------------

class TestLoadSchemaIndex(unittest.TestCase):

    def test_carga_correctamente(self):
        index = load_schema_index(SCHEMA_DIR)
        self.assertIn("capas", index)
        self.assertEqual(len(index["capas"]), 6)

    def test_error_si_directorio_inexistente(self):
        with self.assertRaises(FileNotFoundError):
            load_schema_index(Path("/ruta/que/no/existe"))

    def test_capas_tienen_campos_requeridos(self):
        index = load_schema_index(SCHEMA_DIR)
        for entrada in index["capas"]:
            with self.subTest(capa=entrada.get("nombre")):
                self.assertIn("nombre", entrada)
                self.assertIn("archivo_json", entrada)
                self.assertIn("schema", entrada)


# ---------------------------------------------------------------------------
# validate_layer
# ---------------------------------------------------------------------------

class TestValidateLayer(unittest.TestCase):

    @unittest.skipUnless(_PARCELA_OK, "Piloto PARCELA no disponible")
    def test_capa_valida_parcela(self):
        issues = validate_layer(
            expediente_path=PILOTO_PARCELA,
            layer_name="hechos_confirmados",
            layer_file="capas/hechos_confirmados.json",
            schema_file="hechos_confirmados.schema.json",
            schema_dir=SCHEMA_DIR,
        )
        self.assertEqual(issues, [])

    @unittest.skipUnless(_NAVE222_OK, "Piloto NAVE-222 no disponible")
    def test_capa_valida_nave222(self):
        issues = validate_layer(
            expediente_path=PILOTO_NAVE222,
            layer_name="normativa_aplicable",
            layer_file="capas/normativa_aplicable.json",
            schema_file="normativa_aplicable.schema.json",
            schema_dir=SCHEMA_DIR,
        )
        self.assertEqual(issues, [])

    def test_archivo_inexistente_devuelve_error(self):
        issues = validate_layer(
            expediente_path=PILOTO_PARCELA,
            layer_name="hechos_confirmados",
            layer_file="capas/no_existe.json",
            schema_file="hechos_confirmados.schema.json",
            schema_dir=SCHEMA_DIR,
        )
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "ERROR")
        self.assertEqual(issues[0].code, "LAYER_NOT_FOUND")

    def test_json_mal_formado_devuelve_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            capas_dir = tmp_path / "capas"
            capas_dir.mkdir()
            bad_json = capas_dir / "hechos_confirmados.json"
            bad_json.write_text("{esto no es json valido", encoding="utf-8")

            issues = validate_layer(
                expediente_path=tmp_path,
                layer_name="hechos_confirmados",
                layer_file="capas/hechos_confirmados.json",
                schema_file="hechos_confirmados.schema.json",
                schema_dir=SCHEMA_DIR,
            )
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "ERROR")
        self.assertEqual(issues[0].code, "JSON_PARSE_ERROR")

    def test_schema_inexistente_devuelve_error(self):
        issues = validate_layer(
            expediente_path=PILOTO_PARCELA,
            layer_name="hechos_confirmados",
            layer_file="capas/hechos_confirmados.json",
            schema_file="schema_que_no_existe.schema.json",
            schema_dir=SCHEMA_DIR,
        )
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "SCHEMA_NOT_FOUND")

    def test_campo_requerido_ausente_devuelve_error(self):
        """Hecho sin campo 'id' debe generar error de validacion."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            capas_dir = tmp_path / "capas"
            capas_dir.mkdir()
            datos = [
                {
                    "categoria": "promotor",
                    "campo": "razon_social",
                    "valor": "Empresa X",
                    "estado": "CONFIRMADO",
                    "fuentes": ["DOC-001"],
                }
            ]
            (capas_dir / "hechos_confirmados.json").write_text(
                json.dumps(datos), encoding="utf-8"
            )
            issues = validate_layer(
                expediente_path=tmp_path,
                layer_name="hechos_confirmados",
                layer_file="capas/hechos_confirmados.json",
                schema_file="hechos_confirmados.schema.json",
                schema_dir=SCHEMA_DIR,
            )
        errores = [i for i in issues if i.severity == "ERROR"]
        self.assertGreater(len(errores), 0)
        self.assertTrue(all(i.code == "SCHEMA_VALIDATION_ERROR" for i in errores))

    def test_ruta_de_error_es_legible(self):
        """La ruta en el ValidationIssue debe contener informacion del contexto."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            capas_dir = tmp_path / "capas"
            capas_dir.mkdir()
            datos = [
                {
                    "id": "HC-001",
                    "categoria": "promotor",
                    "campo": "razon_social",
                    "valor": "Empresa X",
                    "estado": "ESTADO_INVENTADO",
                    "fuentes": ["DOC-001"],
                }
            ]
            (capas_dir / "hechos_confirmados.json").write_text(
                json.dumps(datos), encoding="utf-8"
            )
            issues = validate_layer(
                expediente_path=tmp_path,
                layer_name="hechos_confirmados",
                layer_file="capas/hechos_confirmados.json",
                schema_file="hechos_confirmados.schema.json",
                schema_dir=SCHEMA_DIR,
            )
        self.assertGreater(len(issues), 0)
        # La ruta debe contener al menos algun elemento (indice o nombre de campo)
        paths = [i.path for i in issues]
        self.assertTrue(any(p != "<raiz>" for p in paths))


# ---------------------------------------------------------------------------
# validate_expediente — pilotos reales
# ---------------------------------------------------------------------------

@unittest.skipUnless(_PARCELA_OK or _NAVE222_OK, "Pilotos PARCELA y NAVE-222 no disponibles")
class TestValidateExpedientePilotos(unittest.TestCase):

    @unittest.skipUnless(_PARCELA_OK, "Piloto PARCELA no disponible")
    def test_parcela_es_valido(self):
        result = validate_expediente(PILOTO_PARCELA, schema_dir=SCHEMA_DIR)
        self.assertTrue(
            result.is_valid(),
            f"Piloto PARCELA no valido:\n{result.summary()}",
        )

    @unittest.skipUnless(_NAVE222_OK, "Piloto NAVE-222 no disponible")
    def test_nave222_es_valido(self):
        result = validate_expediente(PILOTO_NAVE222, schema_dir=SCHEMA_DIR)
        self.assertTrue(
            result.is_valid(),
            f"Piloto NAVE-222 no valido:\n{result.summary()}",
        )

    @unittest.skipUnless(_PARCELA_OK, "Piloto PARCELA no disponible")
    def test_parcela_zero_errores(self):
        result = validate_expediente(PILOTO_PARCELA, schema_dir=SCHEMA_DIR)
        self.assertEqual(result.error_count(), 0)

    @unittest.skipUnless(_NAVE222_OK, "Piloto NAVE-222 no disponible")
    def test_nave222_zero_errores(self):
        result = validate_expediente(PILOTO_NAVE222, schema_dir=SCHEMA_DIR)
        self.assertEqual(result.error_count(), 0)

    @unittest.skipUnless(_PARCELA_OK, "Piloto PARCELA no disponible")
    def test_schema_version_es_21(self):
        result = validate_expediente(PILOTO_PARCELA, schema_dir=SCHEMA_DIR)
        self.assertEqual(result.schema_version, "2.1")

    @unittest.skipUnless(_PARCELA_OK, "Piloto PARCELA no disponible")
    def test_expediente_path_en_resultado(self):
        result = validate_expediente(PILOTO_PARCELA, schema_dir=SCHEMA_DIR)
        self.assertEqual(result.expediente_path, PILOTO_PARCELA.resolve())


# ---------------------------------------------------------------------------
# validate_expediente — casos de error
# ---------------------------------------------------------------------------

class TestValidateExpedienteErrores(unittest.TestCase):

    def test_capa_faltante_genera_error(self):
        """Expediente sin una capa obligatoria debe generar ERROR."""
        clone = _clone_expediente(PILOTO_NAVE222)
        try:
            capa = clone / "capas" / "hechos_confirmados.json"
            capa.unlink()
            result = validate_expediente(clone, schema_dir=SCHEMA_DIR)
            self.assertFalse(result.is_valid())
            codes = [i.code for i in result.issues]
            self.assertIn("LAYER_NOT_FOUND", codes)
        finally:
            shutil.rmtree(clone.parent, ignore_errors=True)

    def test_json_invalido_genera_error(self):
        """Capa con JSON corrupto debe generar ERROR."""
        clone = _clone_expediente(PILOTO_NAVE222)
        try:
            capa = clone / "capas" / "normativa_aplicable.json"
            capa.write_text("{ json roto !!!", encoding="utf-8")
            result = validate_expediente(clone, schema_dir=SCHEMA_DIR)
            self.assertFalse(result.is_valid())
            codes = [i.code for i in result.issues]
            self.assertIn("JSON_PARSE_ERROR", codes)
        finally:
            shutil.rmtree(clone.parent, ignore_errors=True)

    def test_campo_requerido_ausente_genera_error(self):
        """Capa con un item sin campo requerido debe generar ERROR."""
        clone = _clone_expediente(PILOTO_PARCELA)
        try:
            capa = clone / "capas" / "hechos_confirmados.json"
            datos = json.loads(capa.read_text(encoding="utf-8"))
            # Eliminar campo 'estado' del primer item
            del datos[0]["estado"]
            capa.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            result = validate_expediente(clone, schema_dir=SCHEMA_DIR)
            self.assertFalse(result.is_valid())
        finally:
            shutil.rmtree(clone.parent, ignore_errors=True)

    def test_directorio_inexistente_genera_error(self):
        result = validate_expediente(
            Path("/ruta/que/no/existe/expediente"),
            schema_dir=SCHEMA_DIR,
        )
        self.assertFalse(result.is_valid())
        self.assertGreater(result.error_count(), 0)

    def test_summary_de_resultado_invalido_es_util(self):
        clone = _clone_expediente(PILOTO_NAVE222)
        try:
            capa = clone / "capas" / "hechos_confirmados.json"
            capa.unlink()
            result = validate_expediente(clone, schema_dir=SCHEMA_DIR)
            s = result.summary()
            self.assertIn("NO VALIDO", s)
            self.assertIn("hechos_confirmados", s)
        finally:
            shutil.rmtree(clone.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
