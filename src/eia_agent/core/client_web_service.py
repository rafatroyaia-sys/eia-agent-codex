"""
client_web_service -- punto de entrada desplegable de EIA-Agent Cliente.

Genera una interfaz generica para proyectos nuevos y sirve frontend + API
desde el mismo dominio. Pensado para Docker/Render y despliegues equivalentes.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from eia_agent.core.client_app_package import PROFESSIONAL_MAP_REQUIREMENTS
from eia_agent.core.client_backend import serve_client_backend
from eia_agent.core.client_form_schema import build_client_form_schema
from eia_agent.core.client_new_project_app import (
    build_new_project_app_html,
    build_new_project_blueprint,
)
from eia_agent.core.expediente_initializer import initialize_expediente


def build_deploy_static_site(output_dir: str | Path) -> Path:
    """Genera el frontend generico que se publica junto al backend."""
    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="eia-agent-template-") as tmp:
        template_exp = Path(tmp) / "EXPEDIENTE-PLANTILLA-WEB"
        initialize_expediente(template_exp, expediente_id="EXPEDIENTE-PLANTILLA-WEB")
        schema = build_client_form_schema(template_exp)
        maps = [dict(item, status="PENDIENTE", available=False) for item in PROFESSIONAL_MAP_REQUIREMENTS]
        html = build_new_project_app_html(schema, maps)
        (target / "index.html").write_text(html, encoding="utf-8")
        (target / "nuevo_expediente.html").write_text(html, encoding="utf-8")
        data_dir = target / "data"
        data_dir.mkdir(exist_ok=True)
        import json

        (data_dir / "new_project_blueprint.json").write_text(
            json.dumps(build_new_project_blueprint(schema, maps), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return target


def main() -> None:
    """Arranca el servicio web usando variables de entorno de despliegue."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "10000"))
    workspace = Path(os.getenv("EIA_DATA_DIR", "/var/data")).resolve()
    default_static = Path(tempfile.gettempdir()) / "eia-agent-client-web"
    static_dir = Path(os.getenv("EIA_STATIC_DIR", str(default_static))).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    build_deploy_static_site(static_dir)
    serve_client_backend(workspace=workspace, static_dir=static_dir, host=host, port=port)


if __name__ == "__main__":
    main()
