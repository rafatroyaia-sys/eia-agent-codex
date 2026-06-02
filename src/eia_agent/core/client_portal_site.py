"""
client_portal_site -- exportador HTML estatico del portal cliente.

Genera una pagina autocontenida a partir del contrato client_portal. Sirve como
primer entregable visual para cliente sin necesidad de servidor ni frontend.

No ejecuta fases, no interpreta juridicamente y no declara aptitud administrativa.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from eia_agent.core.client_portal import ClientPortal, build_client_portal


CLIENT_PORTAL_SITE_DIR = "portal_cliente"
CLIENT_PORTAL_SITE_HTML = "index.html"

DISCLAIMER = (
    "Este portal no declara el expediente apto para presentacion administrativa. "
    "Solo organiza el flujo cliente y los outputs existentes."
)


def _text(value: Any) -> str:
    return escape(str(value if value is not None else ""))


def _status_class(status: str) -> str:
    normalized = str(status or "").upper()
    if "BLOQUEADO" in normalized or "ESPERANDO" in normalized:
        return "danger"
    if "LISTO" in normalized:
        return "ok"
    return "warn"


def _priority_class(priority: str) -> str:
    normalized = str(priority or "").upper()
    if normalized == "ALTA":
        return "danger"
    if normalized == "MEDIA":
        return "warn"
    return "muted"


def _progress(counts: dict[str, Any]) -> tuple[int, int, int]:
    total = int(counts.get("total") or 0)
    complete = int(counts.get("complete") or 0)
    pct = int(round((complete / total) * 100)) if total else 0
    return complete, total, pct


def _render_upload_sections(portal: ClientPortal) -> str:
    rows = []
    for section in portal.upload_sections:
        rows.append(
            "<tr>"
            f"<td><strong>{_text(section.section_id)}</strong></td>"
            f"<td><span class='pill {_priority_class(section.priority)}'>{_text(section.priority)}</span></td>"
            f"<td>{_text(section.kind)}</td>"
            f"<td><span class='pill'>{_text(section.status)}</span></td>"
            f"<td>{_text(section.title)}<small>{_text(section.help_text)}</small></td>"
            f"<td><code>{_text(section.target)}</code></td>"
            "</tr>"
        )
    return "\n".join(rows)


def _render_steps(portal: ClientPortal) -> str:
    cards = []
    for step in portal.next_steps:
        priority = step.get("priority", "MEDIA")
        cards.append(
            "<article class='step'>"
            f"<span class='step-order'>{_text(step.get('order'))}</span>"
            f"<div><div class='step-head'><strong>{_text(step.get('title'))}</strong>"
            f"<span class='pill {_priority_class(priority)}'>{_text(priority)}</span></div>"
            f"<p>{_text(step.get('detail'))}</p>"
            f"<small>{_text(step.get('audience'))}</small></div>"
            "</article>"
        )
    return "\n".join(cards)


def _render_artifacts(portal: ClientPortal) -> str:
    items = []
    for artifact in portal.artifacts:
        available = bool(artifact.get("available"))
        label = "disponible" if available else "pendiente"
        cls = "ok" if available else "muted"
        items.append(
            "<li>"
            f"<span class='pill {cls}'>{label}</span>"
            f"<strong>{_text(artifact.get('label') or artifact.get('artifact_id'))}</strong>"
            f"<code>{_text(artifact.get('path'))}</code>"
            "</li>"
        )
    return "\n".join(items)


def _render_warnings(portal: ClientPortal) -> str:
    if not portal.warnings:
        return ""
    items = "\n".join(f"<li>{_text(warning)}</li>" for warning in portal.warnings)
    return f"<section class='band warning'><h2>Avisos</h2><ul>{items}</ul></section>"


def build_client_portal_html(portal: ClientPortal) -> str:
    """Renderiza HTML estatico autocontenido para cliente."""
    counts = portal.intake.get("counts", {})
    complete, total, pct = _progress(counts)
    status_cls = _status_class(portal.status)
    available = sum(1 for artifact in portal.artifacts if artifact.get("available"))
    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Portal cliente - {_text(portal.expediente_id)}</title>
  <style>
    :root {{
      --bg: #f4f6f8;
      --panel: #ffffff;
      --ink: #16202a;
      --soft: #667085;
      --line: #d7dde4;
      --ok: #146c43;
      --ok-bg: #dff4e8;
      --warn: #9a5b00;
      --warn-bg: #fff0cf;
      --danger: #a12121;
      --danger-bg: #ffe0df;
      --brand: #155e75;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.45;
    }}
    header {{
      background: #0f2f3a;
      color: white;
      padding: 28px 32px;
    }}
    header h1 {{
      margin: 0 0 10px;
      font-size: 28px;
      letter-spacing: 0;
    }}
    header p {{ margin: 0; max-width: 980px; color: #d9eef4; }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}
    .card, .band {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    .card h2, .band h2 {{
      margin: 0 0 10px;
      font-size: 16px;
      letter-spacing: 0;
    }}
    .metric {{
      font-size: 28px;
      font-weight: 700;
      margin-top: 6px;
    }}
    .soft {{ color: var(--soft); }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr);
      gap: 18px;
      margin-bottom: 18px;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 700;
    }}
    .pill {{
      display: inline-flex;
      padding: 3px 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .danger {{ background: var(--danger-bg); color: var(--danger); border-color: #f3b4b2; }}
    .warn {{ background: var(--warn-bg); color: var(--warn); border-color: #f0c36b; }}
    .ok {{ background: var(--ok-bg); color: var(--ok); border-color: #a8dbc0; }}
    .muted {{ background: #eef1f4; color: #4f5d6b; }}
    .progress {{
      width: 100%;
      height: 12px;
      border-radius: 999px;
      background: #e7ecf1;
      overflow: hidden;
      margin: 14px 0 8px;
    }}
    .progress > div {{
      height: 100%;
      width: {pct}%;
      background: var(--brand);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      text-align: left;
      padding: 11px 8px;
      vertical-align: top;
    }}
    th {{
      color: var(--soft);
      font-size: 12px;
      text-transform: uppercase;
    }}
    td small {{
      display: block;
      margin-top: 4px;
      color: var(--soft);
    }}
    code {{
      font-family: Consolas, Monaco, monospace;
      color: #344054;
      overflow-wrap: anywhere;
    }}
    .steps {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .step {{
      display: grid;
      grid-template-columns: 38px minmax(0, 1fr);
      gap: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: white;
    }}
    .step-order {{
      width: 34px;
      height: 34px;
      border-radius: 999px;
      background: #e7f3f6;
      color: var(--brand);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
    }}
    .step-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
    }}
    .step p {{ margin: 6px 0; color: var(--soft); }}
    .artifacts {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .artifacts li {{
      display: grid;
      gap: 5px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: white;
    }}
    .warning {{ border-color: #f0c36b; }}
    footer {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 0 24px 28px;
      color: var(--soft);
      font-size: 13px;
    }}
    @media (max-width: 900px) {{
      .hero, .grid, .steps, .artifacts {{ grid-template-columns: 1fr; }}
      header {{ padding: 22px 20px; }}
      main {{ padding: 16px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Portal cliente</h1>
    <p>{_text(portal.expediente_id)}</p>
  </header>
  <main>
    <section class="hero">
      <div class="band">
        <span class="status {status_cls}">{_text(portal.status)}</span>
        <h2>Lectura ejecutiva</h2>
        <p>{_text(portal.headline)}</p>
        <h2>Accion principal</h2>
        <p>{_text(portal.primary_action)}</p>
      </div>
      <div class="band">
        <h2>Completitud de entrada</h2>
        <div class="metric">{complete}/{total}</div>
        <div class="progress"><div></div></div>
        <p class="soft">{pct}% de requisitos completos. administrative_ready: false.</p>
      </div>
    </section>
    <section class="grid">
      <div class="card"><h2>Pendientes</h2><div class="metric">{_text(counts.get('pending', 0))}</div></div>
      <div class="card"><h2>ALTA no completos</h2><div class="metric">{_text(counts.get('high_pending', 0))}</div></div>
      <div class="card"><h2>Artefactos</h2><div class="metric">{available}/{len(portal.artifacts)}</div></div>
      <div class="card"><h2>Listo inicial</h2><div class="metric">{_text(str(portal.intake.get('ready_for_initial_processing', False)))}</div></div>
    </section>
    <section class="band">
      <h2>Entrada cliente</h2>
      <table>
        <thead>
          <tr><th>ID</th><th>Prioridad</th><th>Tipo</th><th>Estado</th><th>Requisito</th><th>Destino</th></tr>
        </thead>
        <tbody>
          {_render_upload_sections(portal)}
        </tbody>
      </table>
    </section>
    <section class="band">
      <h2>Siguientes pasos</h2>
      <div class="steps">
        {_render_steps(portal)}
      </div>
    </section>
    <section class="band">
      <h2>Artefactos</h2>
      <ul class="artifacts">
        {_render_artifacts(portal)}
      </ul>
    </section>
    {_render_warnings(portal)}
  </main>
  <footer>{_text(DISCLAIMER)}</footer>
</body>
</html>
"""
    return html


def write_client_portal_site(
    expediente_path: str | Path,
    portal: ClientPortal | None = None,
) -> Path:
    """Escribe portal_cliente/index.html dentro de documento/."""
    exp = Path(expediente_path)
    portal = portal or build_client_portal(exp)
    out_dir = exp / "documento" / CLIENT_PORTAL_SITE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / CLIENT_PORTAL_SITE_HTML
    html_path.write_text(build_client_portal_html(portal), encoding="utf-8")
    return html_path
