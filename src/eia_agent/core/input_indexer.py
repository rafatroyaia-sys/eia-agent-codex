"""
input_indexer -- IN-05
Escanea la carpeta de entradas de un expediente y genera un índice estructurado
de documentos disponibles, con tipo detectado, parser asignado y resumen de
extracción (cuando aplica).

No usa IA. No escribe automáticamente. Solo lectura, salvo llamada explícita
a write_inputs_index().

Uso:
    from eia_agent.core.input_indexer import build_inputs_index, write_inputs_index

    index = build_inputs_index("expediente-EIA-2026-RECIMETAL-PARCELA")
    print(index.summary())
    write_inputs_index(index, "expediente-EIA-2026-RECIMETAL-PARCELA/inputs/inputs_index.json")
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_IGNORED_FILENAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})
_IGNORED_PREFIXES = ("~$",)

# Mapeo extensión → parser
_PARSER_MAP: dict[str, str | None] = {
    ".docx": "docx_parser",
    ".doc":  "docx_parser",
    ".pdf":  "pdf_parser_pendiente",
    ".png":  "image_no_parser",
    ".jpg":  "image_no_parser",
    ".jpeg": "image_no_parser",
    ".tif":  "image_no_parser",
    ".tiff": "image_no_parser",
}

# Status asignado por extensión (antes del intento de parseo)
_STATUS_BY_EXT: dict[str, str] = {
    ".pdf":  "PENDIENTE_PARSER_PDF",
    ".png":  "REGISTRADO_SIN_PARSER",
    ".jpg":  "REGISTRADO_SIN_PARSER",
    ".jpeg": "REGISTRADO_SIN_PARSER",
    ".tif":  "REGISTRADO_SIN_PARSER",
    ".tiff": "REGISTRADO_SIN_PARSER",
}

# Palabras clave para detección de tipo documental por ruta/nombre.
# Orden: de más específico a más general — el primer match gana.
_TYPE_PATTERNS: list[tuple[str, list[str]]] = [
    ("proyecto_tecnico", ["memoria técnica", "memoria tecnica", "proyecto técnico", "proyecto tecnico",
                          "proyecto_tecnico"]),
    ("memoria",          ["documento_ambiental", "documento ambiental", "estudio ambiental",
                          "memoria", "estudio"]),
    ("cartografia",      ["sig", "shp", "shapefile", "geotiff", "geojson", "kml", "kmz"]),
    ("plano",            ["plano", "planos", "cartografia", "cartografía", "mapa"]),
    ("certificado",      ["certificado", "autorización", "autorizacion", "licencia", "permiso"]),
    ("catastro",         ["catastro", "catastral", "referencia catastral"]),
    ("normativa",        ["normativa", "legislación", "legislacion", "ley", "decreto", "boe", "boc"]),
    ("fotografia",       ["foto", "fotografia", "fotografía", "imagen", "photo"]),
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class InputDocument:
    """Registro de un documento de entrada en el expediente."""
    doc_id: str
    filename: str
    relative_path: str
    extension: str
    size_bytes: int
    sha256: str
    detected_type: str
    status: str
    parser: str | None
    notes: list[str] = field(default_factory=list)
    extracted_summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class InputsIndex:
    """Índice de documentos de entrada de un expediente."""
    expediente_id: str
    base_path: str
    documents: list[InputDocument] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def document_count(self) -> int:
        return len(self.documents)

    def by_type(self, detected_type: str) -> list[InputDocument]:
        return [d for d in self.documents if d.detected_type == detected_type]

    def by_extension(self, extension: str) -> list[InputDocument]:
        ext = extension if extension.startswith(".") else f".{extension}"
        return [d for d in self.documents if d.extension == ext]

    def summary(self) -> str:
        if not self.documents:
            return f"Expediente {self.expediente_id!r}: sin documentos de entrada."
        counts_type: dict[str, int] = {}
        counts_status: dict[str, int] = {}
        for doc in self.documents:
            counts_type[doc.detected_type] = counts_type.get(doc.detected_type, 0) + 1
            counts_status[doc.status] = counts_status.get(doc.status, 0) + 1
        type_str = ", ".join(f"{t}:{n}" for t, n in sorted(counts_type.items()))
        status_str = ", ".join(f"{s}:{n}" for s, n in sorted(counts_status.items()))
        warn_str = f" | {len(self.warnings)} aviso(s)" if self.warnings else ""
        return (
            f"Expediente {self.expediente_id!r}: "
            f"{self.document_count()} documento(s) — "
            f"Tipos: [{type_str}] | Estado: [{status_str}]{warn_str}"
        )

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "base_path": self.base_path,
            "documents": [d.to_dict() for d in self.documents],
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    """Calcula el SHA-256 hex de un archivo."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_document_type(path: Path) -> str:
    """Detecta el tipo documental por nombre de archivo y ruta."""
    combined = (str(path).lower().replace("\\", "/")
                .replace("_", " ").replace("-", " "))
    for doc_type, keywords in _TYPE_PATTERNS:
        if any(kw in combined for kw in keywords):
            return doc_type
    return "desconocido"


def detect_parser(extension: str) -> str | None:
    """Devuelve el parser asignado a una extensión."""
    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    return _PARSER_MAP.get(ext, None)


def _is_ignored(path: Path) -> bool:
    """True si el archivo debe ignorarse."""
    name = path.name
    if name in _IGNORED_FILENAMES:
        return True
    if any(name.startswith(p) for p in _IGNORED_PREFIXES):
        return True
    return False


def _expediente_id_from_path(expediente_path: Path) -> str:
    """Extrae el ID del expediente del nombre de carpeta."""
    return expediente_path.name


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def build_inputs_index(
    expediente_path: "str | Path",
    inputs_dir: str = "inputs",
    parse_docx: bool = True,
) -> InputsIndex:
    """Escanea la carpeta de entradas y genera un InputsIndex.

    No escribe nada en disco. No modifica archivos existentes.

    Args:
        expediente_path: Ruta raíz del expediente.
        inputs_dir:      Nombre de la subcarpeta de entradas (por defecto "inputs").
        parse_docx:      Si True, parsea DOCX con IN-01/IN-02/IN-03 para
                         rellenar extracted_summary. Si False, solo registra.

    Returns:
        InputsIndex con todos los documentos catalogados.
    """
    expediente_path = Path(expediente_path)
    exp_id = _expediente_id_from_path(expediente_path)
    inputs_path = expediente_path / inputs_dir

    warnings: list[str] = []
    documents: list[InputDocument] = []

    if not inputs_path.exists():
        warnings.append(
            f"Carpeta de entradas no encontrada: {inputs_path}. "
            f"El expediente no tiene documentos de entrada disponibles."
        )
        return InputsIndex(
            expediente_id=exp_id,
            base_path=str(expediente_path),
            documents=[],
            warnings=warnings,
        )

    # Recopilar archivos (excluir ignorados)
    all_files: list[Path] = sorted(
        f for f in inputs_path.rglob("*")
        if f.is_file() and not _is_ignored(f)
    )

    for idx, file_path in enumerate(all_files, start=1):
        doc_id = f"DOC-{idx:03d}"
        ext = file_path.suffix.lower()
        rel = str(file_path.relative_to(expediente_path)).replace("\\", "/")

        try:
            size = file_path.stat().st_size
            checksum = sha256_file(file_path)
        except OSError as exc:
            warnings.append(f"{doc_id}: no se pudo acceder a {rel}: {exc}")
            continue

        detected_type = detect_document_type(file_path)
        parser = detect_parser(ext)

        # Status inicial por extensión
        if ext == ".docx":
            status = "PROCESADO"  # optimista; se actualiza si hay error
        else:
            status = _STATUS_BY_EXT.get(ext, "REGISTRADO_SIN_PARSER")

        doc_notes: list[str] = []
        extracted_summary: dict = {}

        # Parseo profundo solo para DOCX
        if ext == ".docx" and parse_docx:
            try:
                from eia_agent.core.docx_parser import parse_docx as _parse_docx
                from eia_agent.core.entity_extractor import extract_entities_from_docx
                from eia_agent.core.evidence_classifier import classify_entities_from_docx

                docx_content = _parse_docx(file_path)
                extraction = extract_entities_from_docx(file_path)
                classification = classify_entities_from_docx(file_path, doc_id)

                entity_types = sorted({e.entity_type for e in extraction.entities})
                extracted_summary = {
                    "text_chars": len(docx_content.texto),
                    "tables_count": len(docx_content.tablas),
                    "entities_count": len(extraction.entities),
                    "candidate_facts_count": len(classification.facts),
                    "entity_types": entity_types,
                }
                if extraction.warnings:
                    extracted_summary["extraction_warnings"] = extraction.warnings
                if classification.warnings:
                    extracted_summary["classification_warnings"] = classification.warnings

            except Exception as exc:
                status = "ERROR"
                doc_notes.append(f"Error al parsear DOCX: {exc}")
                warnings.append(f"{doc_id} ({rel}): error de parseo — {exc}")

        elif ext == ".docx" and not parse_docx:
            extracted_summary = {}

        documents.append(InputDocument(
            doc_id=doc_id,
            filename=file_path.name,
            relative_path=rel,
            extension=ext,
            size_bytes=size,
            sha256=checksum,
            detected_type=detected_type,
            status=status,
            parser=parser,
            notes=doc_notes,
            extracted_summary=extracted_summary,
        ))

    return InputsIndex(
        expediente_id=exp_id,
        base_path=str(expediente_path),
        documents=documents,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Escritura y carga
# ---------------------------------------------------------------------------

def write_inputs_index(index: InputsIndex, output_path: "str | Path") -> Path:
    """Escribe el InputsIndex como JSON UTF-8 indentado.

    Crea el directorio si no existe. No se llama automáticamente desde
    build_inputs_index().

    Args:
        index:       InputsIndex a serializar.
        output_path: Ruta de destino del JSON.

    Returns:
        Path al archivo escrito.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index.to_dict(), f, ensure_ascii=False, indent=2)
    return output_path


def load_inputs_index(path: "str | Path") -> InputsIndex:
    """Carga un InputsIndex desde JSON previamente generado.

    Args:
        path: Ruta al JSON.

    Returns:
        InputsIndex reconstruido.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError: si el JSON no tiene estructura esperada.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Índice no encontrado: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en {path}: {exc}") from exc

    if not isinstance(data, dict) or "documents" not in data:
        raise ValueError(
            f"Estructura inesperada en {path}: falta clave 'documents'."
        )

    try:
        docs = [
            InputDocument(
                doc_id=d["doc_id"],
                filename=d["filename"],
                relative_path=d["relative_path"],
                extension=d["extension"],
                size_bytes=d["size_bytes"],
                sha256=d["sha256"],
                detected_type=d["detected_type"],
                status=d["status"],
                parser=d.get("parser"),
                notes=d.get("notes", []),
                extracted_summary=d.get("extracted_summary", {}),
            )
            for d in data["documents"]
        ]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Documento malformado en {path}: {exc}") from exc

    return InputsIndex(
        expediente_id=data.get("expediente_id", ""),
        base_path=data.get("base_path", ""),
        documents=docs,
        warnings=data.get("warnings", []),
    )
