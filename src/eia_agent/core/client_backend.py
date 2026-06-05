"""
client_backend -- backend local para la app cliente.

Expone una API HTTP ligera basada en la libreria estandar para crear
expedientes nuevos, registrar la entrada cliente y recibir archivos.

No ejecuta automaticamente fases tecnicas ni declara aptitud administrativa.
"""
from __future__ import annotations

import io
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import zipfile
from datetime import datetime, timezone
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from eia_agent.core.expediente_initializer import initialize_expediente, sanitize_expediente_id


CLIENT_PROJECTS_DIR = "expedientes_cliente"
CLIENT_ENTRY_FILE = "control_interno/entrada_cliente.json"
CLIENT_FILES_INDEX = "control_interno/inventario_archivos_cliente.json"
CLIENT_GENERATION_STATUS = "control_interno/estado_generacion_cliente.json"
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

MAX_UPLOAD_REQUEST_BYTES = 100 * 1024 * 1024
MAX_BACKUP_REQUEST_BYTES = 500 * 1024 * 1024
MAX_BACKUP_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
ESSENTIAL_PROJECT_FIELDS = {
    "project_name": "Nombre del proyecto",
    "promoter": "Promotor / titular",
    "location": "Isla, municipio y direccion",
    "coordinates_wgs84": "Coordenadas WGS84",
    "activity_type": "Tipo de actividad",
    "object_description": "Descripcion del objeto evaluado",
}
REQUIRED_HIGH_DOCUMENTS = {
    "DOC-001": "Memoria tecnica del proyecto",
    "DOC-002": "Memoria de explotacion u operaciones",
    "DOC-004": "Planos o esquemas",
    "DOC-006": "Alternativas estudiadas",
}
GENERATION_STEPS = [
    ("FASE_1", "Procesar memorias y evidencias", ["phase1", "--write"]),
    ("FASE_2", "Cerrar el objeto evaluado", ["phase2", "--write"]),
    ("FASE_3", "Preparar el encuadre normativo", ["phase3", "--write"]),
    ("DOCUMENTO", "Generar borrador tecnico y control documental", ["cliente-da", "--write"]),
]
_GENERATION_LOCK = threading.Lock()
_RUNNING_PROJECTS: set[str] = set()


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


def parse_multipart_form(
    content_type: str,
    body: bytes,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Parsea multipart/form-data sin depender del modulo cgi eliminado en Python 3.13."""
    if not content_type.lower().startswith("multipart/form-data"):
        raise ValueError("Content-Type multipart/form-data requerido")
    message = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + content_type.encode("utf-8") + b"\r\n"
        b"MIME-Version: 1.0\r\n\r\n" + body
    )
    fields: dict[str, str] = {}
    files: list[dict[str, Any]] = []
    if not message.is_multipart():
        raise ValueError("Formulario multipart no valido")
    for part in message.iter_parts():
        field_name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files.append({
                "field_name": str(field_name or "file"),
                "filename": filename,
                "content": payload,
                "content_type": part.get_content_type() or "application/octet-stream",
            })
        elif field_name:
            charset = part.get_content_charset() or "utf-8"
            fields[str(field_name)] = payload.decode(charset, errors="replace")
    return fields, files


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


def storage_status(workspace: str | Path) -> dict[str, Any]:
    """Describe el almacenamiento operativo sin prometer persistencia inexistente."""
    root = _projects_root(workspace)
    root.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(root)
    persistent = os.getenv("EIA_PERSISTENT_STORAGE", "").strip().lower() in {"1", "true", "yes", "si"}
    return {
        "mode": "PERSISTENT" if persistent else "TEMPORARY_WITH_BACKUPS",
        "persistent": persistent,
        "workspace": str(Path(workspace).resolve()),
        "free_bytes": usage.free,
        "total_bytes": usage.total,
        "message": (
            "Almacenamiento permanente activo con copias diarias de Render."
            if persistent
            else "Almacenamiento temporal: descargue una copia completa de cada expediente."
        ),
    }


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


def build_project_backup(workspace: str | Path, project_id: str) -> Path:
    """Crea una copia ZIP completa y restaurable del expediente."""
    exp_path = _expediente_path(workspace, project_id)
    if not exp_path.exists():
        raise FileNotFoundError(f"Proyecto no encontrado: {project_id}")
    backup_dir = Path(workspace).resolve() / "copias_seguridad"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{exp_path.name}_COPIA_COMPLETA_{timestamp}.zip"
    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(exp_path.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=str(Path(exp_path.name) / path.relative_to(exp_path)))
    return backup_path


def restore_project_backup(workspace: str | Path, filename: str, content: bytes) -> ClientBackendProject:
    """Restaura una copia generada por la app, validando rutas y estructura."""
    if not filename.lower().endswith(".zip"):
        raise ValueError("La copia debe ser un archivo ZIP")
    projects_root = _projects_root(workspace)
    projects_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        files = [info for info in archive.infolist() if not info.is_dir()]
        if not files:
            raise ValueError("La copia ZIP esta vacia")
        if sum(info.file_size for info in files) > MAX_BACKUP_UNCOMPRESSED_BYTES:
            raise ValueError("La copia supera el tamano maximo permitido")
        roots = {Path(info.filename.replace("\\", "/")).parts[0] for info in files if Path(info.filename).parts}
        if len(roots) != 1:
            raise ValueError("La copia no contiene un unico expediente")
        project_id = sanitize_expediente_id(next(iter(roots)))
        if not project_id:
            raise ValueError("No se pudo identificar el expediente")
        exp_path = _expediente_path(workspace, project_id).resolve()
        for info in files:
            relative = Path(info.filename.replace("\\", "/"))
            if relative.parts[0] != project_id:
                raise ValueError("La copia contiene rutas no validas")
            target = (projects_root / relative).resolve()
            if projects_root.resolve() not in target.parents:
                raise ValueError("La copia contiene una ruta no permitida")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
    entry = _read_json_file(exp_path / CLIENT_ENTRY_FILE)
    return ClientBackendProject(
        project_id=project_id,
        project_name=_project_name(entry),
        expediente_path=str(exp_path),
        status="PROJECT_RESTORED",
        administrative_ready=False,
        warnings=[],
    )


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


def get_backend_project(workspace: str | Path, project_id: str) -> dict[str, Any]:
    """Devuelve la entrada guardada y su estado para reanudar el trabajo."""
    exp_path = _expediente_path(workspace, project_id)
    if not exp_path.exists():
        raise FileNotFoundError(f"Proyecto no encontrado: {project_id}")
    return {
        "project_id": exp_path.name,
        "entry": _read_json_file(exp_path / CLIENT_ENTRY_FILE),
        "readiness": build_project_readiness(workspace, project_id),
        "generation": get_generation_status(workspace, project_id),
        "administrative_ready": False,
    }


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def build_project_readiness(workspace: str | Path, project_id: str) -> dict[str, Any]:
    """Valida los minimos reales guardados antes de ejecutar el motor."""
    exp_path = _expediente_path(workspace, project_id)
    if not exp_path.exists():
        raise FileNotFoundError(f"Proyecto no encontrado: {project_id}")
    entry = _read_json_file(exp_path / CLIENT_ENTRY_FILE)
    project = entry.get("project", {}) if isinstance(entry.get("project"), dict) else {}
    files = _read_upload_index(exp_path)
    uploaded_ids = {str(item.get("control_id") or "") for item in files}
    missing_fields = [
        {"field": key, "label": label}
        for key, label in ESSENTIAL_PROJECT_FIELDS.items()
        if not str(project.get(key) or "").strip()
    ]
    coordinate_value = str(project.get("coordinates_wgs84") or "").strip()
    coordinate_ok = bool(re.fullmatch(
        r"-?\d{1,2}(?:[.,]\d+)?\s*,\s*-?\d{1,3}(?:[.,]\d+)?",
        coordinate_value,
    ))
    missing_documents = [
        {"control_id": key, "label": label}
        for key, label in REQUIRED_HIGH_DOCUMENTS.items()
        if key not in uploaded_ids
    ]
    blockers = [
        *[f"Falta dato esencial: {item['label']}" for item in missing_fields],
        *[f"Falta documento prioritario: {item['label']}" for item in missing_documents],
    ]
    if coordinate_value and not coordinate_ok:
        blockers.append("Las coordenadas WGS84 no tienen un formato reconocible")
    return {
        "project_id": sanitize_expediente_id(project_id),
        "ready_for_generation": not blockers,
        "administrative_ready": False,
        "missing_fields": missing_fields,
        "missing_documents": missing_documents,
        "coordinate_format_ok": coordinate_ok,
        "uploaded_files": len(files),
        "blockers": blockers,
        "note": (
            "Superar esta validacion permite generar un borrador tecnico. "
            "La aptitud administrativa exige cerrar todos los gates y la auditoria final."
        ),
    }


def _generation_status_path(exp_path: Path) -> Path:
    return exp_path / CLIENT_GENERATION_STATUS


def _write_generation_status(exp_path: Path, data: dict[str, Any]) -> None:
    path = _generation_status_path(exp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_generated_outputs(exp_path: Path) -> list[dict[str, Any]]:
    """Lista entregables descargables producidos por el motor."""
    outputs: list[dict[str, Any]] = []
    allowed = {".docx", ".pdf", ".zip"}
    for folder_name in ("output", "documento"):
        folder = exp_path / folder_name
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in allowed:
                continue
            rel = str(path.relative_to(exp_path)).replace("\\", "/")
            name_lower = path.name.lower()
            if name_lower == "documento_ambiental_final_revisable.docx":
                kind, label, priority = "EDITABLE_WORD", "Word editable final", 0
            elif path.suffix.lower() == ".docx":
                kind, label, priority = "EDITABLE_WORD", "Word editable", 1
            elif path.suffix.lower() == ".zip":
                kind, label, priority = "COMPLETE_PACKAGE", "Paquete completo", 2
            else:
                kind, label, priority = "PDF", "PDF de consulta", 3
            outputs.append({
                "name": path.name,
                "relative_path": rel,
                "size_bytes": path.stat().st_size,
                "kind": kind,
                "label": label,
                "editable": path.suffix.lower() == ".docx",
                "priority": priority,
                "download_url": f"/api/projects/{exp_path.name}/outputs/{rel}",
            })
    return sorted(outputs, key=lambda item: (item["priority"], item["name"].lower()))


def get_generation_status(workspace: str | Path, project_id: str) -> dict[str, Any]:
    exp_path = _expediente_path(workspace, project_id)
    if not exp_path.exists():
        raise FileNotFoundError(f"Proyecto no encontrado: {project_id}")
    status = _read_json_file(_generation_status_path(exp_path))
    if not status:
        status = {
            "project_id": sanitize_expediente_id(project_id),
            "status": "NOT_STARTED",
            "message": "La generacion todavia no se ha iniciado.",
            "administrative_ready": False,
            "steps": [],
        }
    status["outputs"] = list_generated_outputs(exp_path)
    return status


def _run_generation(workspace: Path, project_id: str) -> None:
    exp_path = _expediente_path(workspace, project_id)
    runner = Path(__file__).resolve().parents[3] / "run_expediente.py"
    started = datetime.now(timezone.utc).isoformat()
    status: dict[str, Any] = {
        "project_id": sanitize_expediente_id(project_id),
        "status": "RUNNING",
        "message": "Validacion superada. Procesando el expediente.",
        "started_at": started,
        "administrative_ready": False,
        "steps": [],
    }
    _write_generation_status(exp_path, status)
    try:
        for step_id, label, args in GENERATION_STEPS:
            status["current_step"] = step_id
            status["message"] = label
            _write_generation_status(exp_path, status)
            result = subprocess.run(
                [sys.executable, str(runner), str(exp_path), *args],
                cwd=str(runner.parent),
                capture_output=True,
                text=True,
                timeout=1800,
                check=False,
            )
            step = {
                "step_id": step_id,
                "label": label,
                "return_code": result.returncode,
                "status": "OK" if result.returncode == 0 else "BLOCKED",
                "summary": (result.stdout or result.stderr or "").strip()[-2000:],
            }
            status["steps"].append(step)
            if result.returncode != 0:
                status["status"] = "BLOCKED"
                status["message"] = (
                    f"El proceso se detuvo en '{label}'. Revise los datos o documentos pendientes."
                )
                break
        else:
            status["status"] = "COMPLETED_WITH_REVIEW"
            status["message"] = (
                "Borrador tecnico generado. Debe revisarse y superar la auditoria final "
                "antes de presentarlo."
            )
    except Exception as exc:
        status["status"] = "FAILED"
        status["message"] = f"No se pudo completar la generacion: {exc}"
    finally:
        status["finished_at"] = datetime.now(timezone.utc).isoformat()
        status["administrative_ready"] = False
        _write_generation_status(exp_path, status)
        with _GENERATION_LOCK:
            _RUNNING_PROJECTS.discard(sanitize_expediente_id(project_id))


def start_project_generation(workspace: str | Path, project_id: str) -> dict[str, Any]:
    """Inicia la generacion en segundo plano si los minimos estan completos."""
    readiness = build_project_readiness(workspace, project_id)
    if not readiness["ready_for_generation"]:
        return {
            "started": False,
            "status": "BLOCKED",
            "readiness": readiness,
            "administrative_ready": False,
        }
    safe_id = sanitize_expediente_id(project_id)
    with _GENERATION_LOCK:
        if safe_id in _RUNNING_PROJECTS:
            return {
                "started": False,
                "status": "RUNNING",
                "message": "El expediente ya se esta procesando.",
                "administrative_ready": False,
            }
        _RUNNING_PROJECTS.add(safe_id)
    thread = threading.Thread(
        target=_run_generation,
        args=(Path(workspace).resolve(), safe_id),
        daemon=True,
        name=f"eia-generate-{safe_id}",
    )
    thread.start()
    return {
        "started": True,
        "status": "RUNNING",
        "message": "Generacion iniciada. La aplicacion mostrara el avance.",
        "administrative_ready": False,
    }


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
    access_token: str = ""

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-EIA-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _send_file(self, path: Path) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{_safe_filename(path.name)}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not self.access_token:
            return True
        supplied = self.headers.get("X-EIA-Key", "")
        return secrets.compare_digest(supplied, self.access_token)

    def _require_authorized(self) -> bool:
        if self._authorized():
            return True
        self._send_json({"error": "Clave de acceso no valida"}, status=HTTPStatus.UNAUTHORIZED)
        return False

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json({"ok": True})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({
                "ok": True,
                "service": "EIA-Agent Client Backend",
                "storage": storage_status(self.workspace),
                "administrative_ready": False,
                "disclaimer": DISCLAIMER,
            })
            return
        if parsed.path == "/api/storage":
            if not self._require_authorized():
                return
            self._send_json({"storage": storage_status(self.workspace)})
            return
        if parsed.path == "/api/projects":
            if not self._require_authorized():
                return
            self._send_json({"projects": list_backend_projects(self.workspace), "administrative_ready": False})
            return
        match_project = re.fullmatch(r"/api/projects/([^/]+)", parsed.path)
        if match_project:
            if not self._require_authorized():
                return
            project = get_backend_project(self.workspace, unquote(match_project.group(1)))
            self._send_json({"project": project})
            return
        match_readiness = re.fullmatch(r"/api/projects/([^/]+)/readiness", parsed.path)
        if match_readiness:
            if not self._require_authorized():
                return
            readiness = build_project_readiness(self.workspace, unquote(match_readiness.group(1)))
            self._send_json({"readiness": readiness})
            return
        match_status = re.fullmatch(r"/api/projects/([^/]+)/generation-status", parsed.path)
        if match_status:
            if not self._require_authorized():
                return
            status = get_generation_status(self.workspace, unquote(match_status.group(1)))
            self._send_json({"generation": status})
            return
        match_output = re.fullmatch(r"/api/projects/([^/]+)/outputs/(.+)", parsed.path)
        if match_output:
            if not self._require_authorized():
                return
            exp_path = _expediente_path(self.workspace, unquote(match_output.group(1))).resolve()
            candidate = (exp_path / unquote(match_output.group(2))).resolve()
            if exp_path not in candidate.parents or not candidate.is_file():
                self._send_json({"error": "Archivo no encontrado"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_file(candidate)
            return
        match_backup = re.fullmatch(r"/api/projects/([^/]+)/backup", parsed.path)
        if match_backup:
            if not self._require_authorized():
                return
            backup = build_project_backup(self.workspace, unquote(match_backup.group(1)))
            self._send_file(backup)
            return
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if not self._require_authorized():
                return
            if parsed.path == "/api/projects":
                payload = self._read_json_body()
                project = create_project_from_payload(self.workspace, payload)
                self._send_json({"project": project.to_dict()}, status=HTTPStatus.CREATED)
                return
            if parsed.path == "/api/projects/restore":
                self._handle_restore()
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
            match_start = re.fullmatch(r"/api/projects/([^/]+)/generate", parsed.path)
            if match_start:
                result = start_project_generation(self.workspace, unquote(match_start.group(1)))
                status = HTTPStatus.ACCEPTED if result.get("started") else HTTPStatus.CONFLICT
                self._send_json({"generation": result}, status=status)
                return
            self._send_json({"error": "Ruta API no encontrada"}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json({"error": str(exc), "administrative_ready": False}, status=HTTPStatus.BAD_REQUEST)

    def _handle_upload(self, project_id: str) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > MAX_UPLOAD_REQUEST_BYTES:
            raise ValueError("Tamano de subida no permitido")
        fields, files = parse_multipart_form(
            self.headers.get("Content-Type", ""),
            self.rfile.read(length),
        )
        control_id = str(fields.get("control_id") or "DOC-001")
        file_item = next((item for item in files if item["field_name"] == "file"), None)
        if file_item is None:
            raise ValueError("No se recibio archivo")
        content_type = file_item["content_type"] or mimetypes.guess_type(file_item["filename"])[0] or "application/octet-stream"
        saved = save_project_upload(
            self.workspace,
            project_id,
            control_id,
            file_item["filename"],
            file_item["content"],
            content_type,
        )
        self._send_json({"file": saved.to_dict(), "administrative_ready": False}, status=HTTPStatus.CREATED)

    def _handle_restore(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > MAX_BACKUP_REQUEST_BYTES:
            raise ValueError("Tamano de copia no permitido")
        _, files = parse_multipart_form(
            self.headers.get("Content-Type", ""),
            self.rfile.read(length),
        )
        file_item = next((item for item in files if item["field_name"] == "backup"), None)
        if file_item is None:
            raise ValueError("No se recibio la copia de seguridad")
        project = restore_project_backup(
            self.workspace,
            file_item["filename"],
            file_item["content"],
        )
        self._send_json({"project": project.to_dict()}, status=HTTPStatus.CREATED)

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


def build_backend_handler(
    workspace: str | Path,
    static_dir: str | Path,
    access_token: str | None = None,
) -> type[ClientBackendHandler]:
    """Crea una clase handler parametrizada con workspace y carpeta estatica."""
    workspace_path = Path(workspace).resolve()
    static_path = Path(static_dir).resolve()
    token_value = access_token or os.getenv("EIA_ACCESS_TOKEN", "")

    class BoundClientBackendHandler(ClientBackendHandler):
        workspace = workspace_path
        static_dir = static_path
        access_token = token_value

    return BoundClientBackendHandler


def serve_client_backend(
    workspace: str | Path,
    static_dir: str | Path,
    host: str = "127.0.0.1",
    port: int = CLIENT_BACKEND_PORT,
    access_token: str | None = None,
) -> ThreadingHTTPServer:
    """Arranca el servidor HTTP bloqueante para la app cliente."""
    static_path = Path(static_dir).resolve()
    if not static_path.exists():
        raise FileNotFoundError(f"No existe la carpeta estatica: {static_path}")
    handler = build_backend_handler(workspace, static_path, access_token=access_token)
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
