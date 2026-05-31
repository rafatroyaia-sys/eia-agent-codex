"""
Tests NL-01 -- JSON Schema v2.1 para las 6 capas del sistema EIA-Agent.
Ejecutar: venv/Scripts/python -m unittest tests.test_schemas_v21

Los tests validan:
  1. Los 7 archivos schema existen
  2. Todos los schemas son JSON valido
  3. Draft202012Validator.check_schema() pasa
  4. Los pilotos PARCELA y NAVE-222 validan sin errores
  5. Ejemplos invalidos fallan correctamente
"""
import json
import sys
import unittest
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import jsonschema
    from jsonschema import Draft202012Validator, ValidationError
    _JSONSCHEMA_OK = True
except ImportError:
    _JSONSCHEMA_OK = False

# ---------------------------------------------------------------------------
# Rutas (resolve() garantiza path absoluto, necesario para as_uri())
# ---------------------------------------------------------------------------
PROJECT = Path(__file__).parent.parent.resolve()
SCHEMAS_DIR = PROJECT / "config" / "schemas" / "v2_1"
PILOTO_PARCELA = PROJECT / "expediente-EIA-2026-RECIMETAL-PARCELA" / "capas"
PILOTO_NAVE222 = PROJECT / "expediente-EIA-2026-RECIMETAL-NAVE-222" / "capas"
_PARCELA_OK = PILOTO_PARCELA.exists()
_NAVE222_OK = PILOTO_NAVE222.exists()

SCHEMA_FILES = [
    "common_defs.schema.json",
    "hechos_confirmados.schema.json",
    "inferencias_y_gaps.schema.json",
    "normativa_aplicable.schema.json",
    "matriz_trazabilidad.schema.json",
    "cartografia_trace.schema.json",
    "salidas_generadas.schema.json",
]

CAPAS = [
    ("hechos_confirmados.json",   "hechos_confirmados.schema.json"),
    ("inferencias_y_gaps.json",   "inferencias_y_gaps.schema.json"),
    ("normativa_aplicable.json",  "normativa_aplicable.schema.json"),
    ("matriz_trazabilidad.json",  "matriz_trazabilidad.schema.json"),
    ("cartografia_trace.json",    "cartografia_trace.schema.json"),
    ("salidas_generadas.json",    "salidas_generadas.schema.json"),
]


# ---------------------------------------------------------------------------
# Helpers de validacion
# ---------------------------------------------------------------------------

def _load_schema(schema_filename: str) -> dict:
    """Carga un schema desde SCHEMAS_DIR."""
    return json.loads((SCHEMAS_DIR / schema_filename).read_text(encoding="utf-8"))


def _build_store() -> dict:
    """Pre-carga todos los schemas del directorio en un store por file URI.

    Los 6 schemas de capa no tienen $id, por lo que sus $ref relativos
    se resuelven desde la base file://.../schemas/v2_1/<schema>.schema.json.
    common_defs.schema.json se registra bajo su file URI, que es el URI
    al que resuelven los $ref 'common_defs.schema.json#/...' en los otros schemas.
    """
    store: dict = {}
    for f in SCHEMAS_DIR.glob("*.schema.json"):
        schema = json.loads(f.read_text(encoding="utf-8"))
        store[f.as_uri()] = schema
    return store


def _validate_data(data, schema_filename: str) -> list:
    """Valida data contra schema_filename.

    Devuelve lista de strings con los errores encontrados (vacia si OK).
    """
    schema = _load_schema(schema_filename)
    store = _build_store()
    base_uri = (SCHEMAS_DIR / schema_filename).as_uri()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        resolver = jsonschema.RefResolver(
            base_uri=base_uri,
            referrer=schema,
            store=store,
        )
        validator = Draft202012Validator(schema, resolver=resolver)
        return [
            f"{list(e.absolute_path)}: {e.message}"
            for e in validator.iter_errors(data)
        ]


# ---------------------------------------------------------------------------
# 1. Existencia de archivos
# ---------------------------------------------------------------------------

class TestSchemaFilesExist(unittest.TestCase):

    def test_todos_los_schemas_existen(self):
        for fname in SCHEMA_FILES:
            with self.subTest(archivo=fname):
                path = SCHEMAS_DIR / fname
                self.assertTrue(path.exists(), f"No existe: {path}")

    def test_schema_index_existe(self):
        path = SCHEMAS_DIR / "schema_index.json"
        self.assertTrue(path.exists(), f"No existe: {path}")


# ---------------------------------------------------------------------------
# 2. JSON valido
# ---------------------------------------------------------------------------

class TestSchemasJsonValido(unittest.TestCase):

    def test_todos_los_schemas_son_json_valido(self):
        for fname in SCHEMA_FILES:
            with self.subTest(archivo=fname):
                path = SCHEMAS_DIR / fname
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    self.fail(f"{fname} tiene JSON invalido: {e}")

    def test_schema_index_es_json_valido(self):
        path = SCHEMAS_DIR / "schema_index.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            self.fail(f"schema_index.json tiene JSON invalido: {e}")
        self.assertIn("capas", data)
        self.assertEqual(len(data["capas"]), 6)


# ---------------------------------------------------------------------------
# 3. check_schema Draft 2020-12
# ---------------------------------------------------------------------------

@unittest.skipUnless(_JSONSCHEMA_OK, "jsonschema no instalado")
class TestSchemasCheckSchema(unittest.TestCase):

    def test_check_schema_todos(self):
        for fname in SCHEMA_FILES:
            with self.subTest(archivo=fname):
                schema = _load_schema(fname)
                try:
                    Draft202012Validator.check_schema(schema)
                except Exception as e:
                    self.fail(f"{fname} falla check_schema: {e}")


# ---------------------------------------------------------------------------
# 4. Validacion contra pilotos
# ---------------------------------------------------------------------------

@unittest.skipUnless(_JSONSCHEMA_OK and _PARCELA_OK, "jsonschema no instalado o piloto PARCELA no disponible")
class TestValidacionPilotoParcela(unittest.TestCase):

    def _validar_capa(self, capa_file, schema_file):
        path = PILOTO_PARCELA / capa_file
        self.assertTrue(path.exists(), f"No existe capa: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        errores = _validate_data(data, schema_file)
        self.assertEqual(
            errores, [],
            f"Piloto PARCELA / {capa_file} fallo validacion:\n" + "\n".join(errores),
        )

    def test_hechos_confirmados(self):
        self._validar_capa("hechos_confirmados.json", "hechos_confirmados.schema.json")

    def test_inferencias_y_gaps(self):
        self._validar_capa("inferencias_y_gaps.json", "inferencias_y_gaps.schema.json")

    def test_normativa_aplicable(self):
        self._validar_capa("normativa_aplicable.json", "normativa_aplicable.schema.json")

    def test_matriz_trazabilidad(self):
        self._validar_capa("matriz_trazabilidad.json", "matriz_trazabilidad.schema.json")

    def test_cartografia_trace(self):
        self._validar_capa("cartografia_trace.json", "cartografia_trace.schema.json")

    def test_salidas_generadas(self):
        self._validar_capa("salidas_generadas.json", "salidas_generadas.schema.json")


@unittest.skipUnless(_JSONSCHEMA_OK and _NAVE222_OK, "jsonschema no instalado o piloto NAVE-222 no disponible")
class TestValidacionPilotoNave222(unittest.TestCase):

    def _validar_capa(self, capa_file, schema_file):
        path = PILOTO_NAVE222 / capa_file
        self.assertTrue(path.exists(), f"No existe capa: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        errores = _validate_data(data, schema_file)
        self.assertEqual(
            errores, [],
            f"Piloto NAVE-222 / {capa_file} fallo validacion:\n" + "\n".join(errores),
        )

    def test_hechos_confirmados(self):
        self._validar_capa("hechos_confirmados.json", "hechos_confirmados.schema.json")

    def test_inferencias_y_gaps(self):
        self._validar_capa("inferencias_y_gaps.json", "inferencias_y_gaps.schema.json")

    def test_normativa_aplicable(self):
        self._validar_capa("normativa_aplicable.json", "normativa_aplicable.schema.json")

    def test_matriz_trazabilidad(self):
        self._validar_capa("matriz_trazabilidad.json", "matriz_trazabilidad.schema.json")

    def test_cartografia_trace(self):
        self._validar_capa("cartografia_trace.json", "cartografia_trace.schema.json")

    def test_salidas_generadas(self):
        self._validar_capa("salidas_generadas.json", "salidas_generadas.schema.json")


# ---------------------------------------------------------------------------
# 5. Ejemplos invalidos -- deben fallar
# ---------------------------------------------------------------------------

@unittest.skipUnless(_JSONSCHEMA_OK, "jsonschema no instalado")
class TestEjemplosInvalidos(unittest.TestCase):

    def _assert_invalido(self, data, schema_file, motivo=""):
        errores = _validate_data(data, schema_file)
        self.assertGreater(
            len(errores), 0,
            f"Se esperaba error de validacion ({motivo}) pero el dato fue VALIDO",
        )

    def test_hecho_sin_id_es_invalido(self):
        datos = [
            {
                "categoria": "promotor",
                "campo": "razon_social",
                "valor": "Empresa X",
                "estado": "CONFIRMADO",
                "fuentes": ["DOC-001"],
            }
        ]
        self._assert_invalido(datos, "hechos_confirmados.schema.json", "falta id")

    def test_hecho_con_estado_desconocido_es_invalido(self):
        datos = [
            {
                "id": "HC-001",
                "categoria": "promotor",
                "campo": "razon_social",
                "valor": "Empresa X",
                "estado": "INVENTADO",
                "fuentes": ["DOC-001"],
            }
        ]
        self._assert_invalido(datos, "hechos_confirmados.schema.json", "estado invalido")

    def test_hecho_con_fuentes_vacias_es_invalido(self):
        datos = [
            {
                "id": "HC-001",
                "categoria": "promotor",
                "campo": "razon_social",
                "valor": "Empresa X",
                "estado": "CONFIRMADO",
                "fuentes": [],
            }
        ]
        self._assert_invalido(datos, "hechos_confirmados.schema.json", "fuentes vacio")

    def test_normativa_sin_estado_es_invalida(self):
        datos = [
            {
                "id": "NJ-001",
                "tipo": "ley_estatal",
                "norma": "Ley 21/2013 de evaluacion ambiental",
            }
        ]
        self._assert_invalido(datos, "normativa_aplicable.schema.json", "falta estado")

    def test_normativa_con_estado_desconocido_es_invalida(self):
        datos = [
            {
                "id": "NJ-001",
                "tipo": "ley_estatal",
                "norma": "Ley 21/2013 de evaluacion ambiental",
                "estado": "DESCONOCIDO",
            }
        ]
        self._assert_invalido(datos, "normativa_aplicable.schema.json", "estado invalido")

    def test_cartografia_sin_archivo_resultado_es_invalida(self):
        datos = [
            {
                "id": "CT-001",
                "titulo": "Coordenadas de parcela",
                "tipo_cartografia": "VERIFICACION_INTERNA",
                "estado": "VERIFICADO",
            }
        ]
        self._assert_invalido(
            datos, "cartografia_trace.schema.json", "falta archivo_resultado"
        )

    def test_salida_con_fecha_invalida_es_invalida(self):
        datos = [
            {
                "id": "SG-001",
                "fase": "Fase 2",
                "agente": "AG-04",
                "fecha": "12/04/2026",
                "tipo": "ficha_objeto_evaluado",
                "nombre_archivo": "control_interno/ficha.md",
                "descripcion": "Ficha de objeto evaluado",
            }
        ]
        self._assert_invalido(datos, "salidas_generadas.schema.json", "fecha formato incorrecto")

    def test_trazabilidad_sin_estado_evidencia_es_invalida(self):
        datos = [
            {
                "id": "TR-001",
                "dato": "referencia_catastral",
                "valor": "2462105DS4026S0001AQ",
                "fuente_primaria": "DOC-001",
            }
        ]
        self._assert_invalido(
            datos, "matriz_trazabilidad.schema.json", "falta estado_evidencia"
        )

    def test_gap_con_tipo_desconocido_es_invalido(self):
        datos = [
            {
                "id": "GAP-001",
                "tipo": "tipo_inventado_que_no_existe",
                "criticidad": "ALTA",
                "campo": "algun_campo",
            }
        ]
        self._assert_invalido(datos, "inferencias_y_gaps.schema.json", "tipo invalido")

    def test_raiz_objeto_en_lugar_de_array_es_invalida(self):
        """El raiz debe ser siempre array, no objeto."""
        datos = {
            "id": "HC-001",
            "categoria": "promotor",
            "campo": "x",
            "valor": "y",
            "estado": "CONFIRMADO",
            "fuentes": ["DOC-001"],
        }
        self._assert_invalido(datos, "hechos_confirmados.schema.json", "raiz debe ser array")


if __name__ == "__main__":
    unittest.main()
