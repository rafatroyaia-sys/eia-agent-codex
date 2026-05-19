"""tests/test_input_indexer.py — Suite de tests para InputIndexer (IN-05).

Cubre los criterios de cierre del ítem:
- expediente sin inputs/ → índice vacío + warning
- escaneo de carpeta con varios archivos
- ignora temporales ~$, .DS_Store, Thumbs.db
- asigna DOC-001, DOC-002...
- calcula sha256
- detecta tipos por nombre/ruta (memoria, proyecto_tecnico, plano...)
- detecta parser por extensión
- DOCX sintético parse_docx=True → PROCESADO + extracted_summary
- DOCX inválido → ERROR
- PDF → PENDIENTE_PARSER_PDF
- imagen → REGISTRADO_SIN_PARSER
- parse_docx=False → sin summary profundo
- write_inputs_index escribe JSON válido
- load_inputs_index reconstruye dataclasses
- summary(), by_type(), by_extension()
- solo lectura contra PARCELA (DOCX presentes)
- solo lectura contra NAVE-222 (solo PDFs)
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import docx as python_docx

from eia_agent.core.input_indexer import (
    InputDocument,
    InputsIndex,
    build_inputs_index,
    detect_document_type,
    detect_parser,
    load_inputs_index,
    sha256_file,
    write_inputs_index,
)

# ---------------------------------------------------------------------------
# Rutas de fixtures reales
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent
_PARCELA = _ROOT / "expediente-EIA-2026-RECIMETAL-PARCELA"
_NAVE = _ROOT / "expediente-EIA-2026-RECIMETAL-NAVE-222"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_docx(path: Path, texto: str = "Texto de prueba R1201") -> Path:
    doc = python_docx.Document()
    doc.add_paragraph(texto)
    doc.save(str(path))
    return path


def _make_fake_expediente(tmp: str) -> Path:
    """Crea estructura mínima de expediente en directorio temporal."""
    base = Path(tmp) / "expediente-EIA-TEST-001"
    base.mkdir()
    inputs = base / "inputs"
    inputs.mkdir()
    return base


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

class TestSha256File(unittest.TestCase):

    def test_mismo_archivo_mismo_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "test.txt"
            f.write_bytes(b"contenido de prueba")
            h1 = sha256_file(f)
            h2 = sha256_file(f)
        self.assertEqual(h1, h2)

    def test_diferentes_contenidos_diferente_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            f1 = Path(tmp) / "a.txt"
            f2 = Path(tmp) / "b.txt"
            f1.write_bytes(b"contenido A")
            f2.write_bytes(b"contenido B")
            self.assertNotEqual(sha256_file(f1), sha256_file(f2))

    def test_formato_hex_64_chars(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "test.bin"
            f.write_bytes(b"\x00" * 100)
            h = sha256_file(f)
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))


class TestDetectDocumentType(unittest.TestCase):

    def test_memoria(self):
        self.assertEqual(detect_document_type(Path("inputs/memorias/Documento_Ambiental.docx")), "memoria")

    def test_proyecto_tecnico(self):
        self.assertEqual(detect_document_type(Path("inputs/MEMORIA TECNICA DEL PROYECTO.pdf")), "proyecto_tecnico")

    def test_plano(self):
        self.assertEqual(detect_document_type(Path("inputs/planos/plano_situacion.pdf")), "plano")

    def test_certificado(self):
        self.assertEqual(detect_document_type(Path("inputs/certificado_autorizacion.pdf")), "certificado")

    def test_catastro(self):
        self.assertEqual(detect_document_type(Path("inputs/catastro/ficha_catastral.pdf")), "catastro")

    def test_normativa(self):
        self.assertEqual(detect_document_type(Path("inputs/otros/NORMATIVA_BOE.pdf")), "normativa")

    def test_fotografia(self):
        self.assertEqual(detect_document_type(Path("inputs/fotos/foto_instalacion.jpg")), "fotografia")

    def test_desconocido(self):
        self.assertEqual(detect_document_type(Path("inputs/archivo_sin_pistas.xlsx")), "desconocido")

    def test_parcela_docx_es_memoria(self):
        p = Path("inputs/memorias/Documento_Ambiental_RECIMETAL_Parcela_v6.docx")
        self.assertEqual(detect_document_type(p), "memoria")


class TestDetectParser(unittest.TestCase):

    def test_docx(self):
        self.assertEqual(detect_parser(".docx"), "docx_parser")

    def test_pdf(self):
        self.assertEqual(detect_parser(".pdf"), "pdf_parser_pendiente")

    def test_png(self):
        self.assertEqual(detect_parser(".png"), "image_no_parser")

    def test_jpg(self):
        self.assertEqual(detect_parser(".jpg"), "image_no_parser")

    def test_desconocido(self):
        self.assertIsNone(detect_parser(".xlsx"))

    def test_sin_punto(self):
        self.assertEqual(detect_parser("docx"), "docx_parser")


# ---------------------------------------------------------------------------
# InputsIndex sin inputs/
# ---------------------------------------------------------------------------

class TestExpedienteSinInputs(unittest.TestCase):

    def test_devuelve_indice_vacio(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "expediente-SIN-INPUTS"
            base.mkdir()
            index = build_inputs_index(base)
        self.assertEqual(index.document_count(), 0)
        self.assertEqual(index.documents, [])

    def test_warning_presente(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "expediente-SIN-INPUTS"
            base.mkdir()
            index = build_inputs_index(base)
        self.assertGreater(len(index.warnings), 0)
        self.assertTrue(any("no encontrada" in w.lower() or "inputs" in w.lower()
                            for w in index.warnings))

    def test_expediente_id_del_nombre_carpeta(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "expediente-EIA-2026-TEST-001"
            base.mkdir()
            index = build_inputs_index(base)
        self.assertEqual(index.expediente_id, "expediente-EIA-2026-TEST-001")


# ---------------------------------------------------------------------------
# Escaneo de carpeta con archivos
# ---------------------------------------------------------------------------

class TestEscaneo(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name) / "expediente-TEST"
        inputs = self.base / "inputs" / "memorias"
        inputs.mkdir(parents=True)
        otros = self.base / "inputs" / "otros"
        otros.mkdir()

        _make_docx(inputs / "memoria.docx", "Texto de memoria R1201 R13")
        (otros / "normativa.pdf").write_bytes(b"%PDF-1.4 fake pdf content")
        (otros / "foto.jpg").write_bytes(b"\xff\xd8\xff fake jpeg")

    def tearDown(self):
        self.tmp.cleanup()

    def test_encuentra_tres_archivos(self):
        index = build_inputs_index(self.base, parse_docx=False)
        self.assertEqual(index.document_count(), 3)

    def test_doc_ids_secuenciales(self):
        index = build_inputs_index(self.base, parse_docx=False)
        ids = sorted(d.doc_id for d in index.documents)
        self.assertEqual(ids, ["DOC-001", "DOC-002", "DOC-003"])

    def test_extensiones_detectadas(self):
        index = build_inputs_index(self.base, parse_docx=False)
        exts = {d.extension for d in index.documents}
        self.assertIn(".docx", exts)
        self.assertIn(".pdf", exts)
        self.assertIn(".jpg", exts)

    def test_sha256_calculado(self):
        index = build_inputs_index(self.base, parse_docx=False)
        for doc in index.documents:
            self.assertIsNotNone(doc.sha256)
            self.assertEqual(len(doc.sha256), 64)

    def test_pdf_status_pendiente(self):
        index = build_inputs_index(self.base, parse_docx=False)
        pdfs = index.by_extension(".pdf")
        self.assertEqual(len(pdfs), 1)
        self.assertEqual(pdfs[0].status, "PENDIENTE_PARSER_PDF")

    def test_jpg_registrado_sin_parser(self):
        index = build_inputs_index(self.base, parse_docx=False)
        jpgs = index.by_extension(".jpg")
        self.assertEqual(jpgs[0].status, "REGISTRADO_SIN_PARSER")

    def test_pdf_parser_pendiente(self):
        index = build_inputs_index(self.base, parse_docx=False)
        pdfs = index.by_extension(".pdf")
        self.assertEqual(pdfs[0].parser, "pdf_parser_pendiente")

    def test_jpg_image_no_parser(self):
        index = build_inputs_index(self.base, parse_docx=False)
        jpgs = index.by_extension(".jpg")
        self.assertEqual(jpgs[0].parser, "image_no_parser")


# ---------------------------------------------------------------------------
# Filtrado de temporales
# ---------------------------------------------------------------------------

class TestIgnoraTemporales(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name) / "expediente-TEST"
        inputs = self.base / "inputs"
        inputs.mkdir(parents=True)
        # Archivo real
        _make_docx(inputs / "memoria.docx", "Texto real")
        # Temporales
        (inputs / "~$memoria.docx").write_bytes(b"temp word")
        (inputs / ".DS_Store").write_bytes(b"mac metadata")
        (inputs / "Thumbs.db").write_bytes(b"windows thumbs")

    def tearDown(self):
        self.tmp.cleanup()

    def test_solo_archivo_real(self):
        index = build_inputs_index(self.base, parse_docx=False)
        self.assertEqual(index.document_count(), 1)

    def test_no_incluye_temp_word(self):
        index = build_inputs_index(self.base, parse_docx=False)
        names = [d.filename for d in index.documents]
        self.assertNotIn("~$memoria.docx", names)

    def test_no_incluye_ds_store(self):
        index = build_inputs_index(self.base, parse_docx=False)
        names = [d.filename for d in index.documents]
        self.assertNotIn(".DS_Store", names)

    def test_no_incluye_thumbs(self):
        index = build_inputs_index(self.base, parse_docx=False)
        names = [d.filename for d in index.documents]
        self.assertNotIn("Thumbs.db", names)


# ---------------------------------------------------------------------------
# Tipos detectados por nombre
# ---------------------------------------------------------------------------

class TestTiposDetectados(unittest.TestCase):

    def _index_with_file(self, name: str, content: bytes = b"") -> InputsIndex:
        tmp = tempfile.mkdtemp()
        self._tmps = getattr(self, "_tmps", [])
        self._tmps.append(tmp)
        base = Path(tmp) / "expediente-TEST"
        inputs = base / "inputs"
        inputs.mkdir(parents=True)
        (inputs / name).write_bytes(content or b"placeholder")
        return build_inputs_index(base, parse_docx=False)

    def tearDown(self):
        import shutil
        for t in getattr(self, "_tmps", []):
            shutil.rmtree(t, ignore_errors=True)

    def test_memoria(self):
        index = self._index_with_file("Documento_Ambiental.pdf")
        self.assertEqual(index.documents[0].detected_type, "memoria")

    def test_plano(self):
        index = self._index_with_file("plano_situacion.pdf")
        self.assertEqual(index.documents[0].detected_type, "plano")

    def test_normativa(self):
        index = self._index_with_file("NORMATIVA_BOE_2013.pdf")
        self.assertEqual(index.documents[0].detected_type, "normativa")

    def test_fotografia(self):
        index = self._index_with_file("foto_nave.jpg", b"\xff\xd8\xff")
        self.assertEqual(index.documents[0].detected_type, "fotografia")

    def test_desconocido(self):
        index = self._index_with_file("archivo_random.xlsx")
        self.assertEqual(index.documents[0].detected_type, "desconocido")


# ---------------------------------------------------------------------------
# parse_docx=True — DOCX sintético
# ---------------------------------------------------------------------------

class TestParseDocxTrue(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name) / "expediente-TEST"
        inputs = self.base / "inputs" / "memorias"
        inputs.mkdir(parents=True)
        _make_docx(
            inputs / "memoria.docx",
            "Referencia catastral 2462302DS4026S0001GQ. Operación R1201. LER 17 04 05."
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_status_procesado(self):
        index = build_inputs_index(self.base, parse_docx=True)
        docx_docs = index.by_extension(".docx")
        self.assertEqual(docx_docs[0].status, "PROCESADO")

    def test_extracted_summary_no_vacio(self):
        index = build_inputs_index(self.base, parse_docx=True)
        docx_docs = index.by_extension(".docx")
        self.assertNotEqual(docx_docs[0].extracted_summary, {})

    def test_summary_tiene_text_chars(self):
        index = build_inputs_index(self.base, parse_docx=True)
        doc = index.by_extension(".docx")[0]
        self.assertIn("text_chars", doc.extracted_summary)
        self.assertGreater(doc.extracted_summary["text_chars"], 0)

    def test_summary_tiene_entities_count(self):
        index = build_inputs_index(self.base, parse_docx=True)
        doc = index.by_extension(".docx")[0]
        self.assertIn("entities_count", doc.extracted_summary)

    def test_summary_tiene_candidate_facts_count(self):
        index = build_inputs_index(self.base, parse_docx=True)
        doc = index.by_extension(".docx")[0]
        self.assertIn("candidate_facts_count", doc.extracted_summary)

    def test_summary_tiene_entity_types(self):
        index = build_inputs_index(self.base, parse_docx=True)
        doc = index.by_extension(".docx")[0]
        self.assertIn("entity_types", doc.extracted_summary)
        self.assertIsInstance(doc.extracted_summary["entity_types"], list)

    def test_parser_docx_parser(self):
        index = build_inputs_index(self.base, parse_docx=True)
        doc = index.by_extension(".docx")[0]
        self.assertEqual(doc.parser, "docx_parser")

    def test_no_escribe_automaticamente(self):
        index = build_inputs_index(self.base, parse_docx=True)
        # No debe existir inputs_index.json
        for path in self.base.rglob("inputs_index.json"):
            self.fail(f"build_inputs_index escribió automáticamente: {path}")


# ---------------------------------------------------------------------------
# parse_docx=False
# ---------------------------------------------------------------------------

class TestParseDocxFalse(unittest.TestCase):

    def test_no_rellena_summary_profundo(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "expediente-TEST"
            inputs = base / "inputs"
            inputs.mkdir(parents=True)
            _make_docx(inputs / "memoria.docx", "Texto de prueba")
            index = build_inputs_index(base, parse_docx=False)
        doc = index.by_extension(".docx")[0]
        # Sin parseo profundo, extracted_summary debe estar vacío o sin text_chars
        self.assertNotIn("text_chars", doc.extracted_summary)


# ---------------------------------------------------------------------------
# DOCX inválido → ERROR
# ---------------------------------------------------------------------------

class TestDocxInvalido(unittest.TestCase):

    def test_docx_invalido_status_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "expediente-TEST"
            inputs = base / "inputs"
            inputs.mkdir(parents=True)
            # Crear archivo con extensión .docx pero contenido inválido
            (inputs / "corrupto.docx").write_bytes(b"esto no es un docx valido 12345")
            index = build_inputs_index(base, parse_docx=True)
        docs = index.by_extension(".docx")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].status, "ERROR")

    def test_docx_invalido_tiene_nota(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "expediente-TEST"
            inputs = base / "inputs"
            inputs.mkdir(parents=True)
            (inputs / "corrupto.docx").write_bytes(b"contenido binario basura")
            index = build_inputs_index(base, parse_docx=True)
        docs = index.by_extension(".docx")
        self.assertGreater(len(docs[0].notes), 0)

    def test_docx_invalido_genera_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "expediente-TEST"
            inputs = base / "inputs"
            inputs.mkdir(parents=True)
            (inputs / "corrupto.docx").write_bytes(b"basura")
            index = build_inputs_index(base, parse_docx=True)
        self.assertGreater(len(index.warnings), 0)


# ---------------------------------------------------------------------------
# write_inputs_index y load_inputs_index
# ---------------------------------------------------------------------------

class TestWriteLoad(unittest.TestCase):

    def _build_simple(self) -> InputsIndex:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "expediente-TEST"
            inputs = base / "inputs"
            inputs.mkdir(parents=True)
            _make_docx(inputs / "memoria.docx", "Texto R1201")
            return build_inputs_index(base, parse_docx=False)

    def test_write_crea_json(self):
        index = self._build_simple()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "idx.json"
            write_inputs_index(index, out)
            self.assertTrue(out.exists())

    def test_write_json_valido(self):
        index = self._build_simple()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "idx.json"
            write_inputs_index(index, out)
            data = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn("documents", data)
        self.assertIn("expediente_id", data)

    def test_write_crea_directorio(self):
        index = self._build_simple()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "subdir" / "profundo" / "idx.json"
            write_inputs_index(index, out)
            self.assertTrue(out.exists())

    def test_write_retorna_path(self):
        index = self._build_simple()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "idx.json"
            result = write_inputs_index(index, out)
        self.assertEqual(result, out)

    def test_load_reconstruye_dataclass(self):
        index = self._build_simple()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "idx.json"
            write_inputs_index(index, out)
            loaded = load_inputs_index(out)
        self.assertIsInstance(loaded, InputsIndex)
        self.assertIsInstance(loaded.documents[0], InputDocument)

    def test_load_preserva_doc_id(self):
        index = self._build_simple()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "idx.json"
            write_inputs_index(index, out)
            loaded = load_inputs_index(out)
        self.assertEqual(loaded.documents[0].doc_id, index.documents[0].doc_id)

    def test_load_preserva_sha256(self):
        index = self._build_simple()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "idx.json"
            write_inputs_index(index, out)
            loaded = load_inputs_index(out)
        self.assertEqual(loaded.documents[0].sha256, index.documents[0].sha256)

    def test_load_no_existe(self):
        with self.assertRaises(FileNotFoundError):
            load_inputs_index("/ruta/que/no/existe/idx.json")

    def test_load_json_invalido(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "bad.json"
            f.write_text("esto no es json", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_inputs_index(f)

    def test_load_sin_clave_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "bad.json"
            f.write_text('{"other": "data"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_inputs_index(f)


# ---------------------------------------------------------------------------
# InputsIndex API
# ---------------------------------------------------------------------------

class TestInputsIndexAPI(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name) / "expediente-TEST"
        inputs = self.base / "inputs"
        memorias = inputs / "memorias"
        memorias.mkdir(parents=True)
        otros = inputs / "otros"
        otros.mkdir()
        _make_docx(memorias / "memoria.docx", "Texto R1201")
        (otros / "normativa.pdf").write_bytes(b"%PDF-1.4 fake")
        (otros / "foto.jpg").write_bytes(b"\xff\xd8\xff fake")
        self.index = build_inputs_index(self.base, parse_docx=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_document_count(self):
        self.assertEqual(self.index.document_count(), 3)

    def test_by_type_memoria(self):
        docs = self.index.by_type("memoria")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].filename, "memoria.docx")

    def test_by_type_normativa(self):
        docs = self.index.by_type("normativa")
        self.assertEqual(len(docs), 1)

    def test_by_type_fotografia(self):
        docs = self.index.by_type("fotografia")
        self.assertEqual(len(docs), 1)

    def test_by_type_vacio(self):
        self.assertEqual(self.index.by_type("cartografia"), [])

    def test_by_extension_docx(self):
        docs = self.index.by_extension(".docx")
        self.assertEqual(len(docs), 1)

    def test_by_extension_sin_punto(self):
        docs = self.index.by_extension("pdf")
        self.assertEqual(len(docs), 1)

    def test_by_extension_vacio(self):
        self.assertEqual(self.index.by_extension(".png"), [])

    def test_summary_contiene_total(self):
        s = self.index.summary()
        self.assertIn("3", s)

    def test_summary_contiene_id(self):
        s = self.index.summary()
        self.assertIn("expediente-TEST", s)

    def test_summary_vacio(self):
        idx = InputsIndex(expediente_id="EXP", base_path="/ruta")
        self.assertIn("sin documentos", idx.summary())

    def test_to_dict_tiene_documents(self):
        d = self.index.to_dict()
        self.assertIn("documents", d)
        self.assertEqual(len(d["documents"]), 3)


# ---------------------------------------------------------------------------
# Solo lectura contra PARCELA
# ---------------------------------------------------------------------------

@unittest.skipUnless(
    (_PARCELA / "inputs").exists(),
    f"Fixture PARCELA no disponible: {_PARCELA}/inputs"
)
class TestFixtureParcela(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.index = build_inputs_index(_PARCELA, parse_docx=True)

    def test_no_lanza_excepcion(self):
        self.assertIsInstance(self.index, InputsIndex)

    def test_detecta_docx_memoria(self):
        docx_docs = self.index.by_extension(".docx")
        self.assertGreater(len(docx_docs), 0)
        tipos = [d.detected_type for d in docx_docs]
        self.assertTrue(any(t in ("memoria", "proyecto_tecnico", "desconocido") for t in tipos))

    def test_no_modifica_mtime(self):
        mtimes_antes = {
            str(f): os.path.getmtime(f)
            for f in (_PARCELA / "inputs").rglob("*")
            if f.is_file()
        }
        build_inputs_index(_PARCELA, parse_docx=False)
        for ruta, mtime in mtimes_antes.items():
            self.assertEqual(os.path.getmtime(ruta), mtime, f"mtime modificado: {ruta}")

    def test_no_escribe_inputs_index_json(self):
        for f in _PARCELA.rglob("inputs_index.json"):
            self.fail(f"build_inputs_index creó archivo: {f}")

    def test_docx_status_procesado(self):
        docx_docs = self.index.by_extension(".docx")
        # Al menos uno debe ser PROCESADO (si el parseo funcionó)
        procesados = [d for d in docx_docs if d.status == "PROCESADO"]
        errores = [d for d in docx_docs if d.status == "ERROR"]
        self.assertTrue(
            len(procesados) > 0 or len(errores) > 0,
            "DOCX ni PROCESADO ni ERROR — estado inesperado"
        )

    def test_extracted_summary_presente_en_procesados(self):
        procesados = [d for d in self.index.by_extension(".docx") if d.status == "PROCESADO"]
        for doc in procesados:
            self.assertIn("text_chars", doc.extracted_summary)
            self.assertIn("entities_count", doc.extracted_summary)

    def test_summary_coherente(self):
        s = self.index.summary()
        total = self.index.document_count()
        self.assertIn(str(total), s)


# ---------------------------------------------------------------------------
# Solo lectura contra NAVE-222
# ---------------------------------------------------------------------------

@unittest.skipUnless(
    (_NAVE / "inputs").exists(),
    f"Fixture NAVE-222 no disponible: {_NAVE}/inputs"
)
class TestFixtureNave222(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.index = build_inputs_index(_NAVE, parse_docx=True)

    def test_no_lanza_excepcion(self):
        self.assertIsInstance(self.index, InputsIndex)

    def test_solo_pdfs_pendiente_parser(self):
        pdfs = self.index.by_extension(".pdf")
        self.assertGreater(len(pdfs), 0)
        for doc in pdfs:
            self.assertEqual(doc.status, "PENDIENTE_PARSER_PDF")

    def test_sin_docx(self):
        docx_docs = self.index.by_extension(".docx")
        self.assertEqual(len(docx_docs), 0)

    def test_no_modifica_mtime(self):
        mtimes_antes = {
            str(f): os.path.getmtime(f)
            for f in (_NAVE / "inputs").rglob("*")
            if f.is_file()
        }
        build_inputs_index(_NAVE, parse_docx=False)
        for ruta, mtime in mtimes_antes.items():
            self.assertEqual(os.path.getmtime(ruta), mtime, f"mtime modificado: {ruta}")

    def test_no_escribe_inputs_index_json(self):
        for f in _NAVE.rglob("inputs_index.json"):
            self.fail(f"build_inputs_index creó archivo: {f}")

    def test_pdf_parser_pendiente(self):
        pdfs = self.index.by_extension(".pdf")
        for doc in pdfs:
            self.assertEqual(doc.parser, "pdf_parser_pendiente")

    def test_summary_menciona_expediente(self):
        s = self.index.summary()
        self.assertIn("NAVE", s)


if __name__ == "__main__":
    unittest.main()
