"""
client_backend -- backend local para la app cliente.

Expone una API HTTP ligera basada en la libreria estandar para crear
expedientes nuevos, registrar la entrada cliente y recibir archivos.

No ejecuta automaticamente fases tecnicas ni declara aptitud administrativa.
"""
from __future__ import annotations

import cgi
import json
import mimetypes
import re
import shutil
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from eia_agent.core.expediente_initializer import initialize_expediente, sanitize_expediente_id


CLIENT_PROJECTS_DIR = "expedientes_cliente"
CLIENT_ENTRY_FILE = "control_interno/entrada_cliente.json"
CLIENT_FILES_INDEX = "control_interno/inventario_archivos_cliente.json"
CLIENT_BACKEND_PORT = 8765

DISCLAIMER = (
    "El backend crea expedientes, guarda inputs y prepara la ejecucion del motor. "
    "No declara aptitud administrativa."
)

UPLOAD_TARGETS: dict[str, str] = {
    "DOC-001": "inputs/memoria_tecnica",
    "DOC-002": "inputs/memoria_explotacion",
    "DOC-003": "inputs/imagenes",
    "DOC-004": "inputs/cartografia_aportada",
    "DOC-005": "inputs/fotos",
    "DOC-006": "inputs/imagenes",
    "MEDIA-001": "inputs/fotos",
    "CART-001": "inputs/cartografia_aportada",
}


@dataclass
class ClientBackendProject:
    """Proyecto creado por el backend cliente."""

    project_id: str
    project_name: str
    expediente_path: str
    status: str
    administrative_ready: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "expediente_path": self.expediente_path,
            "status": self.status,
            "administrative_ready": False,
            "warnings": list(self.warnings),
            "disclaimer": DISCLAIMER,
        }


@dataclass
class SavedUpload:
    """Archivo recibido para un expediente cliente."""

    control_id: str
    original_name: str
    stored_path: str
    size_bytes: int
    content_type: str = "application/octet-stream"

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "original_name": self.original_name,
            "stored_path": self.stored_path,
            "size_bytes": self.size_bytes,
            "content_type": self.content_type,
        }


def _safe_filename(name: str) -> str:
    cleaned = Path(name or "archivo").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned).strip("._")
    return cleaned or "archivo"


def _project_name(payload: dict[str, Any]) -> str:
    project = payload.get("project")
    if isinstance(project, dict):
        return str(project.get("project_name") or payload.get("project_name") or "nuevo expediente")
    return str(payload.get("project_name") or "nuevo expediente")


def _project_id_from_payload(payload: dict[str, Any]) -> str:
    name = _project_name(payload)
    eid = sanitize_expediente_id(name)
    return f"EXP-{eid}" if eid and not eid.startswith("EXP-") else (eid or "EXP-NUEVO-EXPEDIENTE")


def _projects_root(workspace: str | Path) -> Path:
    return Path(workspace).resolve() / CLIENT_PROJECTS_DIR


def _expediente_path(workspace: str | Path, project_id: str) -> Path:
    return _projects_root(workspace) / sanitize_expediente_id(project_id)


def create_project_from_payload(
    workspace: str | Path,
    payload: dict[str, Any],
    overwrite_entry: bool = True,
) -> ClientBackendProject:
    """Crea estructura de expediente y registra la entrada cliente."""
    project_id = _project_id_from_payload(payload)
    project_name = _project_name(payload)
    exp_path = _expediente_path(workspace, project_id)
    init = initialize_expediente(exp_path, expediente_id=project_id, force=False, with_guides=True)
    warnings = list(init.warnings)
    entry_path = exp_path / CLIENT_ENTRY_FILE
    if entry_path.exists() and not overwrite_entry:
        warnings.append("Ya existia entrada_cliente.json; no se sobrescribio.")
    else:
        entry_path.parent.mkdir(parents=True, exist_ok=True)
        entry = dict(payload)
        entry["backend"] = {
            "project_id": project_id,
            "project_name": project_name,
            "administrative_ready": False,
            "disclaimer": DISCLAIMER,
        }
        entry_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    return ClientBackendProject(
        project_id=project_id,
        project_name=project_name,
        expediente_path=str(exp_path),
        status="PROJECT_CREATED" if init.status in {"CREATED", "ALREADY_EXISTS"} else init.status,
        administrative_ready=False,
        warnings=warnings,
    )


def _read_upload_index(exp_path: Path) -> list[dict[str, Any]]:
    index_path = exp_path / CLIENT_FILES_INDEX
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        files = data.get("files", [])
        return files if isinstance(files, list) else []
    except Exception:
        return []


def _write_upload_index(exp_path: Path, files: list[dict[str, Any]]) -> None:
    index_path = exp_path / CLIENT_FILES_INDEX
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(
            {
                "administrative_ready": False,
                "disclaimer": DISCLAIMER,
                "files": files,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def save_project_upload(
    workspace: str | Path,
    project_id: str,
    control_id: str,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
) -> SavedUpload:
    """Guarda un archivo recibido en la carpeta de inputs correspondiente."""
    exp_path = _expediente_path(workspace, project_id)
    if not exp_path.exists():
        raise FileNotFoundError(f"Proyecto no encontrado: {project_id}")
    target_rel = UPLOAD_TARGETS.get(control_id, "inputs/otros")
    safe_name = _safe_filename(filename)
    target_dir = exp_path / target_rel
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe_name
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        counter = 2
        while target.exists():
            target = target_dir / f"{stem}_{counter}{suffix}"
            counter += 1
    target.write_bytes(content)
    saved = SavedUpload(
        control_id=control_id,
        original_name=filename,
        stored_path=str(target.relative_to(exp_path)).replace("\\", "/"),
        size_bytes=len(content),
        content_type=content_type,
    )
    files = _read_upload_index(exp_path)
    files.append(saved.to_dict())
    _write_upload_index(exp_path, files)
    return saved


def list_backend_projects(workspace: str | Path) -> list[dict[str, Any]]:
    """Lista expedientes creados por el backend cliente."""
    root = _projects_root(workspace)
    if not root.exists():
        return []
    projects: list[dict[str, Any]] = []
    for item in sorted(root.iterdir()):
        if not item.is_dir():
            continue
        entry_path = item / CLIENT_ENTRY_FILE
        project_name = item.name
        if entry_path.exists():
            try:
                entry = json.loads(entry_path.read_text(encoding="utf-8"))
                project = entry.get("project", {})
                if isinstance(project, dict):
                    project_name = str(project.get("project_name") or project_name)
            except Exception:
                pass
        projects.append({
            "project_id": item.name,
            "project_name": project_name,
            "expediente_path": str(item),
            "administrative_ready": False,
        })
    return projects


def build_generate_plan(workspace: str | Path, project_id: str) -> dict[str, Any]:
    """Devuelve la secuencia de ejecucion recomendada para generar el DA."""
    exp_path = _expediente_path(workspace, project_id)
    if not exp_path.exists():
        raise FileNotFoundError(f"Proyecto no encontrado: {project_id}")
    commands = [
        "phase1 --write",
        "phase2 --write",
        "phase3 --write",
        "phase4-offline --write",
        "inventory-build --write",
        "inventory-gate --write",
        "run-technical-pipeline --write",
        "document-manifest --write",
        "document-build-md --write",
        "document-build-docx --write",
        "document-insert-figures --write",
        "document-qc --write",
        "document-package --write",
        "document-export --write",
        "document-prepare-presentation --write",
        "cliente-app-package --write",
    ]
    return {
        "project_id": sanitize_expediente_id(project_id),
        "expediente_path": str(exp_path),
        "commands": commands,
        "administrative_ready": False,
        "disclaimer": DISCLAIMER,
        "note": "Los gates pueden bloquear la ejecucion si faltan datos criticos.",
    }


class ClientBackendHandler(SimpleHTTPRequestHandler):
    """Handler HTTP para servir frontend y API cliente."""

    workspace: Path
    static_dir: Path

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json({"ok": True})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({
                "ok": True,
                "service": "EIA-Agent Client Backend",
                "administrative_ready": False,
                "disclaimer": DISCLAIMER,
            })
            return
        if parsed.path == "/api/projects":
            self._send_json({"projects": list_backend_projects(self.workspace), "administrative_ready": False})
            return
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/projects":
                payload = self._read_json_body()
                project = create_project_from_payload(self.workspace, payload)
                self._send_json({"project": project.to_dict()}, status=HTTPStatus.CREATED)
                return
            match_upload = re.fullmatch(r"/api/projects/([^/]+)/files", parsed.path)
            if match_upload:
                self._handle_upload(unquote(match_upload.group(1)))
                return
            match_generate = re.fullmatch(r"/api/projects/([^/]+)/generate-plan", parsed.path)
            if match_generate:
                plan = build_generate_plan(self.workspace, unquote(match_generate.group(1)))
                self._send_json({"plan": plan})
                return
            self._send_json({"error": "Ruta API no encontrada"}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json({"error": str(exc), "administrative_ready": False}, status=HTTPStatus.BAD_REQUEST)

    def _handle_upload(self, project_id: str) -> None:
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": self.headers.get("Content-Type", ""),
        })
        control_id = str(form.getfirst("control_id") or "DOC-001")
        file_item = form["file"] if "file" in form else None
        if file_item is None or not getattr(file_item, "filename", ""):
            raise ValueError("No se recibio archivo")
        content = file_item.file.read()
        content_type = getattr(file_item, "type", None) or mimetypes.guess_type(file_item.filename)[0] or "application/octet-stream"
        saved = save_project_upload(self.workspace, project_id, control_id, file_item.filename, content, content_type)
        self._send_json({"file": saved.to_dict(), "administrative_ready": False}, status=HTTPStatus.CREATED)

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        rel = unquote(parsed.path.lstrip("/")) or "index.html"
        candidate = (self.static_dir / rel).resolve()
        static_root = self.static_dir.resolve()
        if static_root not in candidate.parents and candidate != static_root:
            return str(static_root / "index.html")
        if candidate.is_dir():
            candidate = candidate / "index.html"
        return str(candidate)


def build_backend_handler(workspace: str | Path, static_dir: str | Path) -> type[ClientBackendHandler]:
    """Crea una clase handler parametrizada con workspace y carpeta estatica."""
    workspace_path = Path(workspace).resolve()
    static_path = Path(static_dir).resolve()

    class BoundClientBackendHandler(ClientBackendHandler):
        workspace = workspace_path
        static_dir = static_path

    return BoundClientBackendHandler


def serve_client_backend(
    workspace: str | Path,
    static_dir: str | Path,
    host: str = "127.0.0.1",
    port: int = CLIENT_BACKEND_PORT,
) -> ThreadingHTTPServer:
    """Arranca el servidor HTTP bloqueante para la app cliente."""
    static_path = Path(static_dir).resolve()
    if not static_path.exists():
        raise FileNotFoundError(f"No existe la carpeta estatica: {static_path}")
    handler = build_backend_handler(workspace, static_path)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"EIA-Agent Client Backend: http://{host}:{port}/")
    print(f"Workspace: {Path(workspace).resolve()}")
    print(f"Static   : {static_path}")
    try:
        server.serve_forever()
    finally:
        server.server_close()


def copy_static_app(source_app_dir: str | Path, target_dir: str | Path) -> Path:
    """Copia la app HTML a una carpeta desplegable."""
    source = Path(source_app_dir)
    target = Path(target_dir)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return target
