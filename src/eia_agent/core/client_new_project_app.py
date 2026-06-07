"""
client_new_project_app -- mesa de entrada para expedientes nuevos.

Genera una app HTML autocontenida para que el cliente prepare un nuevo
expediente ambiental: datos basicos, documentos, fotos, coordenadas,
cartografia requerida, validacion minima y exportacion de paquete de entrada.

No ejecuta fases tecnicas y no declara aptitud administrativa.
"""
from __future__ import annotations

import json
from html import escape
from typing import Any

from eia_agent.core.client_form_schema import ClientFormSchema


DISCLAIMER = (
    "La app prepara la entrada de un nuevo Documento Ambiental y verifica "
    "minimos de entrega. La aptitud administrativa depende del cierre tecnico, "
    "la cartografia oficial, la trazabilidad y la auditoria final conforme."
)


def _text(value: Any) -> str:
    return escape(str(value if value is not None else ""))


def _controls_payload(schema: ClientFormSchema) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for control in schema.controls:
        payload.append({
            "control_id": control.control_id,
            "label": control.label,
            "control_type": control.control_type,
            "priority": control.priority,
            "required": control.required,
            "target": control.target,
            "help_text": control.help_text,
            "accepted_formats": control.accepted_formats,
            "validations": control.validations,
        })
    return payload


def build_new_project_blueprint(
    schema: ClientFormSchema,
    map_requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    """Contrato funcional para crear expedientes nuevos desde UI/API."""
    return {
        "app_name": "EIA-Agent Nuevo Expediente",
        "version": "1.0",
        "administrative_ready": False,
        "disclaimer": DISCLAIMER,
        "minimum_project_fields": [
            "project_name",
            "promoter",
            "location",
            "coordinates_wgs84",
            "activity_type",
            "object_description",
        ],
        "workflow": [
            {
                "step": "alta_proyecto",
                "label": "Alta del proyecto",
                "output": "entrada_cliente.json",
            },
            {
                "step": "carga_documental",
                "label": "Memorias, fotos, coordenadas, planos y anexos",
                "output": "inventario_archivos_cliente.json",
            },
            {
                "step": "validacion_minimos",
                "label": "Control de obligatorios y bloqueantes",
                "output": "checklist_entrada_cliente.md",
            },
            {
                "step": "generacion_tecnica",
                "label": "Ejecucion del motor EIA-Agent por fases",
                "output": "Documento Ambiental DOCX, mapas, climograma y anejos",
            },
        ],
        "controls": _controls_payload(schema),
        "map_requirements": map_requirements,
        "expected_outputs": [
            "documento_ambiental_final_revisable.docx",
            "documento_ambiental_borrador_con_figuras.docx",
            "mapas_png",
            "climograma_png",
            "anejos",
            "auditoria_final",
        ],
    }


def build_new_project_app_html(
    schema: ClientFormSchema,
    map_requirements: list[dict[str, Any]],
) -> str:
    """Renderiza app HTML autocontenida para iniciar expedientes nuevos."""
    controls = _controls_payload(schema)
    upload_controls = [c for c in controls if c["control_type"] == "file_upload"]
    required_uploads = [c for c in upload_controls if c["required"] and c["priority"] == "ALTA"]
    maps = list(map_requirements)
    controls_json = json.dumps(controls, ensure_ascii=False)
    maps_json = json.dumps(maps, ensure_ascii=False)
    disclaimer_json = json.dumps(DISCLAIMER, ensure_ascii=False)
    upload_rows = "\n".join(
        "<tr>"
        f"<td><strong>{_text(c['control_id'])}</strong></td>"
        f"<td>{_text(c['label'])}<small>{_text(c['help_text'])} "
        f"{'Obligatorio.' if c['required'] else 'Recomendado para mejorar el informe.'}</small></td>"
        f"<td><span class='pill {_text(str(c['priority']).lower())}'>{_text(c['priority'])}</span></td>"
        f"<td>{_text(', '.join(c.get('accepted_formats') or ['PDF', 'DOCX', 'PNG', 'JPG']))}</td>"
        f"<td><input id='file-{_text(c['control_id'])}' data-control='{_text(c['control_id'])}' type='file' multiple></td>"
        "</tr>"
        for c in upload_controls
    )
    map_rows = "\n".join(
        "<tr>"
        f"<td><strong>{_text(m.get('map_id'))}</strong></td>"
        f"<td>{_text(m.get('title'))}<small>{_text(m.get('purpose'))}</small></td>"
        f"<td><span class='pill {_text(str(m.get('priority', '')).lower())}'>{_text(m.get('priority'))}</span></td>"
        f"<td>{_text(', '.join(m.get('required_layers') or []))}</td>"
        "</tr>"
        for m in maps
    )
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EIA-Agent - Nuevo expediente ambiental</title>
  <style>
    :root {{
      --bg: #eef4ef;
      --panel: #ffffff;
      --ink: #18251f;
      --muted: #5f6f68;
      --line: #d7e2dc;
      --brand: #1f5f43;
      --brand-2: #2f8f5f;
      --brand-3: #0f3d32;
      --ok: #146c43;
      --warn: #995c00;
      --danger: #a12121;
      --ok-bg: #e1f4e9;
      --warn-bg: #fff0cf;
      --danger-bg: #ffe1df;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.45;
    }}
    header {{
      background:
        linear-gradient(135deg, rgba(15, 61, 50, .96), rgba(20, 83, 67, .94)),
        repeating-linear-gradient(45deg, rgba(255,255,255,.06) 0 1px, transparent 1px 14px);
      color: white;
      padding: 30px 34px;
      border-bottom: 1px solid rgba(255,255,255,.16);
    }}
    .header-inner {{ max-width: 1220px; margin: 0 auto; }}
    header h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: 0; }}
    header p {{ margin: 0; color: #d7edf3; max-width: 980px; }}
    main {{ max-width: 1220px; margin: 0 auto; padding: 24px; }}
    .topbar {{
      display: flex;
      flex-wrap: wrap;
      align-items: end;
      gap: 10px;
      margin-top: 18px;
    }}
    .access-block {{
      display: grid;
      gap: 5px;
      width: min(280px, 100%);
      color: #d7edf3;
      font-size: 12px;
      font-weight: 700;
    }}
    .access-key {{
      width: 100%;
      border-color: rgba(255,255,255,.35);
      background: rgba(255,255,255,.12);
      color: white;
    }}
    .access-key::placeholder {{ color: #d7edf3; }}
    button {{
      border: 1px solid var(--brand);
      background: var(--brand);
      color: white;
      border-radius: 6px;
      padding: 10px 13px;
      font-weight: 700;
      cursor: pointer;
    }}
    button:hover {{ filter: brightness(1.05); }}
    button.secondary {{ background: white; color: var(--brand); }}
    button.ghost {{ background: transparent; color: white; border-color: rgba(255,255,255,.35); }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(260px, 330px) minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 10px 28px rgba(24,37,31,.05);
    }}
    .panel h2 {{ margin: 0 0 12px; font-size: 18px; letter-spacing: 0; }}
    .panel h3 {{ margin: 18px 0 8px; font-size: 15px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .metric {{
      background: white;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      border-left: 5px solid var(--brand-2);
    }}
    .metric strong {{ display: block; font-size: 26px; }}
    .metric span {{ color: var(--muted); font-size: 13px; }}
    .metric.ok {{ border-left-color: var(--ok); background: #fbfffd; }}
    .metric.warn {{ border-left-color: #d99b20; background: #fffdf8; }}
    label {{
      display: grid;
      gap: 6px;
      margin-bottom: 11px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }}
    input, textarea, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      font: inherit;
      color: var(--ink);
      background: white;
    }}
    input:focus, textarea:focus, select:focus {{
      outline: 3px solid rgba(47, 143, 95, .18);
      border-color: var(--brand-2);
    }}
    .field-help {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 400;
      margin-top: -4px;
    }}
    textarea {{ min-height: 110px; resize: vertical; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    td small {{ display: block; color: var(--muted); margin-top: 3px; }}
    .pill {{
      display: inline-flex;
      border-radius: 999px;
      padding: 3px 8px;
      border: 1px solid var(--line);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .alta, .danger {{ background: var(--danger-bg); color: var(--danger); border-color: #f2b4b2; }}
    .media, .warn {{ background: var(--warn-bg); color: var(--warn); border-color: #f0c36b; }}
    .ok {{ background: var(--ok-bg); color: var(--ok); border-color: #a8dbc0; }}
    .muted {{ color: var(--muted); }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }}
    .actions button {{ min-height: 44px; }}
    .table-wrap {{ width: 100%; overflow-x: auto; }}
    .table-wrap table {{ min-width: 850px; }}
    .table-wrap input[type=file] {{ min-width: 220px; }}
    .checklist {{ display: grid; gap: 8px; padding: 0; list-style: none; margin: 0; }}
    .checklist li {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      border-bottom: 1px solid var(--line);
      padding: 8px 0;
    }}
    .project-list {{ display: grid; gap: 8px; }}
    .project-item {{
      width: 100%;
      text-align: left;
      background: #f8fafc;
      color: var(--ink);
      border-color: var(--line);
    }}
    .note {{
      background: #eaf6ee;
      border: 1px solid #bde4c9;
      border-radius: 8px;
      padding: 12px;
      color: #194d33;
      margin-bottom: 14px;
    }}
    .backend-status {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-top: 14px;
      border: 1px solid rgba(255,255,255,.35);
      border-radius: 999px;
      padding: 6px 10px;
      color: #d7edf3;
      font-size: 13px;
      font-weight: 700;
    }}
    .backend-status.ok {{
      background: #e1f4e9;
      color: #0b5d36;
      border-color: #a8dbc0;
    }}
    .backend-status.warn {{
      background: #fff0cf;
      color: #7a4700;
      border-color: #f0c36b;
    }}
    .storage-status {{ margin-left: 8px; }}
    .workflow {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 18px;
    }}
    .workflow-step {{
      background: white;
      border: 1px solid var(--line);
      border-top: 4px solid var(--brand-2);
      border-radius: 6px;
      padding: 12px;
      font-weight: 700;
    }}
    .workflow-step small {{ display: block; color: var(--muted); font-weight: 400; margin-top: 4px; }}
    .guidance {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: center;
      margin-bottom: 18px;
      background: #f8fffa;
      border: 1px solid #bde4c9;
      border-left: 6px solid var(--brand-2);
      border-radius: 8px;
      padding: 14px 16px;
    }}
    .guidance strong {{ display: block; margin-bottom: 3px; }}
    .guidance p {{ margin: 0; color: var(--muted); }}
    .progress-line {{
      height: 10px;
      background: #dce9e1;
      border-radius: 999px;
      min-width: 220px;
      overflow: hidden;
    }}
    .progress-line span {{
      display: block;
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--brand-2), #87c46f);
      border-radius: inherit;
      transition: width .2s ease;
    }}
    .generation-box {{
      border: 1px solid var(--line);
      background: #f8fafc;
      border-radius: 6px;
      padding: 14px;
      margin-top: 14px;
    }}
    .generation-box ul {{ margin: 8px 0 0; padding-left: 20px; }}
    button:disabled {{ opacity: .45; cursor: not-allowed; }}
    @media (max-width: 980px) {{
      .layout, .summary, .workflow {{ grid-template-columns: 1fr; }}
      .guidance {{ grid-template-columns: 1fr; }}
      header {{ padding: 24px 20px; }}
      main {{ padding: 16px; }}
      .topbar button {{ flex: 1 1 210px; }}
      .storage-status {{ margin-left: 0; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <h1>EIA-Agent | Nuevo expediente ambiental</h1>
      <p>Prepare un Documento Ambiental con memorias, coordenadas, fotos, mapas, climograma, medidas, PVA y control de presentacion.</p>
      <div class="topbar">
        <label class="access-block">Clave de acceso
          <input class="access-key" id="access-key" type="password" placeholder="Introduzca la clave facilitada">
        </label>
        <button id="save-project">Guardar borrador local</button>
        <button class="ghost" id="restore-backup">Recuperar copia completa</button>
        <input id="restore-backup-file" type="file" accept=".zip" hidden>
        <button class="ghost" id="reset-form">Nuevo expediente</button>
      </div>
      <div>
        <span class="backend-status" id="backend-status">Servicio: comprobando conexion</span>
        <span class="backend-status storage-status" id="storage-status">Archivos: comprobando proteccion</span>
      </div>
    </div>
  </header>
  <main>
    <section class="workflow">
      <div class="workflow-step">1. Rellenar datos<small>Identificacion, ubicacion y actividad.</small></div>
      <div class="workflow-step">2. Subir documentos<small>Memorias, planos, alternativas y fotos.</small></div>
      <div class="workflow-step">3. Validar expediente<small>La app indica exactamente que falta.</small></div>
      <div class="workflow-step">4. Generar y revisar<small>Borrador tecnico, controles y descarga.</small></div>
    </section>
    <section class="guidance" aria-live="polite">
      <div>
        <strong id="next-action-title">Siguiente paso: rellenar datos esenciales</strong>
        <p id="next-action-copy">Complete identificacion, ubicacion, coordenadas, actividad y objeto evaluado para preparar el expediente.</p>
      </div>
      <div class="progress-line" aria-label="Progreso de entrada"><span id="progress-bar"></span></div>
    </section>
    <section class="summary">
      <div class="metric"><strong id="score-required">0/6</strong><span>Datos esenciales</span></div>
      <div class="metric"><strong id="score-files">0/{len(required_uploads)}</strong><span>Bloques documentales</span></div>
      <div class="metric"><strong>{len(maps)}</strong><span>Mapas/planos esperados</span></div>
      <div class="metric"><strong id="score-status">Pendiente</strong><span>Estado de entrada</span></div>
      <div class="metric"><strong id="backend-project">Sin crear</strong><span>Expediente backend</span></div>
      <div class="metric"><strong id="storage-metric">Comprobando</strong><span>Proteccion de archivos</span></div>
    </section>
    <section class="layout">
      <aside class="panel">
        <h2>Expedientes guardados</h2>
        <div class="project-list" id="project-list"></div>
        <h3>Control de minimos</h3>
        <ul class="checklist" id="checklist"></ul>
      </aside>
      <div>
        <section class="panel">
          <h2>1. Datos del proyecto</h2>
          <div class="note">Los datos introducidos quedan como DECLARADOS hasta que el tecnico los cierre con evidencia y cartografia oficial.</div>
          <label>Nombre del proyecto
            <input id="project_name" data-required="true" placeholder="Ej. Centro de valorizacion de residuos no peligrosos">
            <span class="field-help">Nombre claro que aparecera en portada, indice y expediente.</span>
          </label>
          <label>Promotor / titular
            <input id="promoter" data-required="true" placeholder="Razon social del promotor">
            <span class="field-help">Persona o entidad que presenta el Documento Ambiental.</span>
          </label>
          <label>Isla, municipio y direccion
            <input id="location" data-required="true" placeholder="Municipio, isla, direccion o paraje">
            <span class="field-help">Cuanto mas concreta sea la ubicacion, mejor se preparan mapas y contexto territorial.</span>
          </label>
          <label>Coordenadas WGS84
            <input id="coordinates_wgs84" data-required="true" placeholder="28.000000, -16.000000">
            <span class="field-help">Formato recomendado: latitud, longitud. Ejemplo: 28.123456, -16.123456.</span>
          </label>
          <label>Referencia catastral
            <input id="cadastre_reference" placeholder="Si consta">
          </label>
          <label>Tipo de actividad
            <select id="activity_type" data-required="true">
              <option value="">Seleccionar</option>
              <option>Gestion de residuos</option>
              <option>Actividad industrial</option>
              <option>Infraestructura</option>
              <option>Actividad energetica</option>
              <option>Otra actividad sometida a evaluacion ambiental</option>
            </select>
          </label>
          <label>Descripcion del objeto evaluado
            <textarea id="object_description" data-required="true" placeholder="Operaciones, capacidad, superficies, procesos, accesos, horarios, focos de emision, residuos, agua, energia y elementos incluidos/excluidos"></textarea>
            <span class="field-help">Incluya lo que entra y lo que queda fuera del proyecto; esto evita contradicciones en el informe.</span>
          </label>
        </section>
        <section class="panel">
          <h2>2. Documentacion y archivos</h2>
          <div class="note">Seleccione los archivos antes de pulsar <strong>Guardar expediente y subir archivos</strong>. Puede aportar varios archivos en cada apartado.</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>ID</th><th>Requisito</th><th>Prioridad</th><th>Formatos</th><th>Archivos</th></tr></thead>
              <tbody>{upload_rows}</tbody>
            </table>
          </div>
        </section>
        <section class="panel">
          <h2>3. Cartografia, planos y clima esperados</h2>
          <div class="table-wrap">
            <table>
              <thead><tr><th>ID</th><th>Mapa/plano</th><th>Prioridad</th><th>Capas minimas</th></tr></thead>
              <tbody>{map_rows}</tbody>
            </table>
          </div>
        </section>
        <section class="panel">
          <h2>4. Salida para generar el Documento Ambiental</h2>
          <p class="muted">Primero guarde el expediente y suba los archivos. Despues valide la documentacion. La generacion solo se inicia si no faltan datos o documentos prioritarios.</p>
          <div class="actions">
            <button id="create-backend-bottom">1. Guardar expediente y subir archivos</button>
            <button class="secondary" id="validate-backend">2. Validar documentacion</button>
            <button id="generate-document" disabled>3. Generar Documento Ambiental</button>
            <button class="secondary" id="download-backup" disabled>Descargar copia completa</button>
          </div>
          <div class="generation-box" id="generation-box">
            <strong>Estado: pendiente de guardar y validar</strong>
            <p class="muted">Aqui apareceran los documentos pendientes, el avance y las descargas disponibles.</p>
          </div>
        </section>
      </div>
    </section>
  </main>
  <script>
    const controls = {controls_json};
    const mapRequirements = {maps_json};
    const disclaimer = {disclaimer_json};
    const essentialFields = ['project_name', 'promoter', 'location', 'coordinates_wgs84', 'activity_type', 'object_description'];
    const storageKey = 'eia_agent_client_projects_v1';
    const accessKeyStorage = 'eia_agent_access_key_v1';
    const fieldLabels = {{
      project_name: 'nombre del proyecto',
      promoter: 'promotor o titular',
      location: 'isla, municipio y direccion',
      coordinates_wgs84: 'coordenadas WGS84',
      activity_type: 'tipo de actividad',
      object_description: 'descripcion del objeto evaluado'
    }};
    let backendOnline = false;
    let backendProjectId = '';
    let backendProjects = [];
    let storagePersistent = false;
    function value(id) {{ return document.getElementById(id)?.value?.trim() || ''; }}
    function accessKey() {{ return document.getElementById('access-key')?.value || ''; }}
    function apiHeaders(json = false) {{
      const headers = {{}};
      if (json) headers['Content-Type'] = 'application/json';
      if (accessKey()) headers['X-EIA-Key'] = accessKey();
      return headers;
    }}
    function fileMeta(controlId) {{
      const input = document.getElementById(`file-${{controlId}}`);
      return Array.from(input?.files || []).map((f) => ({{ name: f.name, size_bytes: f.size, type: f.type || 'unknown' }}));
    }}
    function currentProject() {{
      const data = {{
        app: 'EIA-Agent Nuevo Expediente',
        created_at: new Date().toISOString(),
        evidence_state_default: 'DECLARADO',
        administrative_ready: false,
        disclaimer,
        project: {{
          project_name: value('project_name'),
          promoter: value('promoter'),
          location: value('location'),
          coordinates_wgs84: value('coordinates_wgs84'),
          cadastre_reference: value('cadastre_reference'),
          activity_type: value('activity_type'),
          object_description: value('object_description')
        }},
        files: controls.filter((c) => c.control_type === 'file_upload').map((c) => ({{
          control_id: c.control_id,
          label: c.label,
          priority: c.priority,
          required: c.required,
          target: c.target,
          selected_files: fileMeta(c.control_id)
        }})),
        map_requirements: mapRequirements,
        next_engine_step: 'Crear expediente EIA-Agent y ejecutar fases con control de gates'
      }};
      data.validation = validate(data);
      return data;
    }}
    function validate(data) {{
      const missingFields = essentialFields.filter((id) => !data.project[id]);
      const missingFiles = data.files.filter((f) => f.required && f.priority === 'ALTA' && f.selected_files.length === 0).map((f) => f.control_id);
      const coordinateOk = /^-?\\d{{1,2}}([\\.,]\\d+)?\\s*,\\s*-?\\d{{1,3}}([\\.,]\\d+)?$/.test(data.project.coordinates_wgs84 || '');
      const blockers = [...missingFields.map((id) => `Falta dato esencial: ${{id}}`), ...missingFiles.map((id) => `Falta bloque documental ALTA: ${{id}}`)];
      if (data.project.coordinates_wgs84 && !coordinateOk) blockers.push('Formato de coordenadas WGS84 no reconocido');
      return {{
        essential_complete: essentialFields.length - missingFields.length,
        essential_total: essentialFields.length,
        high_files_complete: data.files.filter((f) => f.required && f.priority === 'ALTA' && f.selected_files.length > 0).length,
        high_files_total: data.files.filter((f) => f.required && f.priority === 'ALTA').length,
        coordinate_format_ok: coordinateOk,
        blockers,
        ready_for_engine: blockers.length === 0
      }};
    }}
    function refresh() {{
      const data = currentProject();
      const requiredMetric = document.getElementById('score-required');
      const filesMetric = document.getElementById('score-files');
      const statusMetric = document.getElementById('score-status');
      requiredMetric.textContent = `${{data.validation.essential_complete}}/${{data.validation.essential_total}}`;
      filesMetric.textContent = `${{data.validation.high_files_complete}}/${{data.validation.high_files_total}}`;
      statusMetric.textContent = data.validation.ready_for_engine ? 'Completa' : 'Pendiente';
      requiredMetric.closest('.metric').className = `metric ${{data.validation.essential_complete === data.validation.essential_total ? 'ok' : 'warn'}}`;
      filesMetric.closest('.metric').className = `metric ${{data.validation.high_files_complete === data.validation.high_files_total ? 'ok' : 'warn'}}`;
      statusMetric.closest('.metric').className = `metric ${{data.validation.ready_for_engine ? 'ok' : 'warn'}}`;
      document.getElementById('backend-project').textContent = backendProjectId || 'Sin crear';
      document.getElementById('download-backup').disabled = !backendProjectId;
      updateGuidance(data);
      const list = document.getElementById('checklist');
      list.innerHTML = '';
      const items = [
        ['Datos esenciales', data.validation.essential_complete === data.validation.essential_total],
        ['Coordenadas WGS84 validables', data.validation.coordinate_format_ok],
        ['Documentos ALTA cargados', data.validation.high_files_complete === data.validation.high_files_total],
        ['Catalogo cartografico previsto', mapRequirements.length >= 12],
        ['Aptitud administrativa automatica', false]
      ];
      items.forEach(([label, ok]) => {{
        const li = document.createElement('li');
        li.innerHTML = `<span>${{label}}</span><span class="pill ${{ok ? 'ok' : 'warn'}}">${{ok ? 'OK' : 'Pendiente'}}</span>`;
        list.appendChild(li);
      }});
    }}
    function updateGuidance(data) {{
      const title = document.getElementById('next-action-title');
      const copy = document.getElementById('next-action-copy');
      const progress = document.getElementById('progress-bar');
      const total = data.validation.essential_total + data.validation.high_files_total;
      const done = data.validation.essential_complete + data.validation.high_files_complete;
      progress.style.width = `${{Math.round((done / Math.max(total, 1)) * 100)}}%`;
      const missingFields = essentialFields.filter((id) => !data.project[id]).map((id) => fieldLabels[id] || id);
      if (missingFields.length) {{
        title.textContent = 'Siguiente paso: completar datos esenciales';
        copy.textContent = `Falta: ${{missingFields.slice(0, 3).join(', ')}}${{missingFields.length > 3 ? '...' : ''}}. Estos datos son la base de portada, objeto evaluado y cartografia.`;
        return;
      }}
      const missingHighFiles = data.files.filter((f) => f.required && f.priority === 'ALTA' && f.selected_files.length === 0);
      if (missingHighFiles.length) {{
        title.textContent = 'Siguiente paso: subir documentos prioritarios';
        copy.textContent = `Falta cargar: ${{missingHighFiles.map((f) => f.control_id).join(', ')}}. La app puede seguir con documentos recomendados pendientes, pero no con estos minimos.`;
        return;
      }}
      if (!backendProjectId) {{
        title.textContent = 'Siguiente paso: guardar y subir archivos';
        copy.textContent = 'La entrada minima esta completa. Pulse el boton 1 para crear el expediente y subir la documentacion al servicio.';
        return;
      }}
      const generateDisabled = document.getElementById('generate-document').disabled;
      if (generateDisabled) {{
        title.textContent = 'Siguiente paso: validar documentacion';
        copy.textContent = 'El expediente ya esta guardado. Pulse validar para que la app revise si puede generar el Documento Ambiental.';
        return;
      }}
      title.textContent = 'Siguiente paso: generar Documento Ambiental';
      copy.textContent = 'La app ya puede preparar el borrador tecnico, con Word editable y descargas de control para revision profesional.';
    }}
    function projects() {{ return JSON.parse(localStorage.getItem(storageKey) || '[]'); }}
    function saveProjects(items) {{ localStorage.setItem(storageKey, JSON.stringify(items)); renderProjects(); }}
    function renderProjects() {{
      const box = document.getElementById('project-list');
      const items = projects();
      box.innerHTML = (items.length || backendProjects.length) ? '' : '<p class="muted">No hay expedientes guardados.</p>';
      backendProjects.forEach((item) => {{
        const btn = document.createElement('button');
        btn.className = 'project-item';
        btn.textContent = `${{item.project_name}} · servidor`;
        btn.addEventListener('click', () => loadBackendProject(item.project_id));
        box.appendChild(btn);
      }});
      items.forEach((item, idx) => {{
        const btn = document.createElement('button');
        btn.className = 'project-item';
        btn.textContent = item.project?.project_name || `Proyecto ${{idx + 1}}`;
        btn.addEventListener('click', () => loadProject(item));
        box.appendChild(btn);
      }});
    }}
    async function loadBackendProjects() {{
      if (!backendOnline || !accessKey()) return;
      const res = await fetch('/api/projects', {{ headers: apiHeaders(false), cache: 'no-store' }});
      if (!res.ok) return;
      const body = await res.json();
      backendProjects = body.projects || [];
      renderProjects();
    }}
    async function loadBackendProject(projectId) {{
      const res = await fetch(`/api/projects/${{encodeURIComponent(projectId)}}`, {{
        headers: apiHeaders(false),
        cache: 'no-store'
      }});
      if (!res.ok) {{
        alert('No se pudo abrir el expediente guardado.');
        return;
      }}
      const body = await res.json();
      backendProjectId = body.project.project_id;
      loadProject(body.project.entry || {{}});
      const readiness = body.project.readiness;
      document.getElementById('generate-document').disabled = !readiness.ready_for_generation;
      const generation = body.project.generation;
      const steps = (generation.steps || []).map((step) => `${{step.status}}: ${{step.label}}`);
      renderGeneration(`Estado: ${{generation.status}}`, generation.message, steps, generation.outputs || []);
      refresh();
    }}
    function loadProject(data) {{
      Object.entries(data.project || {{}}).forEach(([id, val]) => {{
        const el = document.getElementById(id);
        if (el) el.value = val || '';
      }});
      refresh();
    }}
    function saveCurrent() {{
      const data = currentProject();
      const items = projects().filter((p) => (p.project?.project_name || '') !== (data.project.project_name || ''));
      items.unshift(data);
      saveProjects(items.slice(0, 20));
      refresh();
    }}
    function download(name, text, type) {{
      const blob = new Blob([text], {{ type }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }}
    function safeName() {{
      return (value('project_name') || 'nuevo_expediente').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'nuevo_expediente';
    }}
    function downloadJson() {{
      const data = currentProject();
      download(`${{safeName()}}_entrada_cliente.json`, JSON.stringify(data, null, 2), 'application/json');
    }}
    function checklistMarkdown() {{
      const data = currentProject();
      const lines = [
        `# Checklist entrada cliente - ${{data.project.project_name || 'Nuevo expediente'}}`,
        '',
        `> ${{disclaimer}}`,
        '',
        '## Estado',
        '',
        `- Datos esenciales: ${{data.validation.essential_complete}}/${{data.validation.essential_total}}`,
        `- Documentos ALTA: ${{data.validation.high_files_complete}}/${{data.validation.high_files_total}}`,
        `- Coordenadas WGS84 validables: ${{data.validation.coordinate_format_ok}}`,
        `- Listo para motor: ${{data.validation.ready_for_engine}}`,
        '- administrative_ready: false',
        '',
        '## Bloqueantes',
        ''
      ];
      if (data.validation.blockers.length) data.validation.blockers.forEach((b) => lines.push(`- ${{b}}`));
      else lines.push('- Sin bloqueantes de entrada detectados por la app.');
      lines.push('', '## Archivos declarados', '');
      data.files.forEach((f) => lines.push(`- ${{f.control_id}} ${{f.label}}: ${{f.selected_files.map((x) => x.name).join(', ') || 'PENDIENTE'}}`));
      lines.push('', '## Mapas esperados', '');
      mapRequirements.forEach((m) => lines.push(`- ${{m.map_id}} ${{m.title}} (${{m.priority}})`));
      return lines.join('\\n');
    }}
    function downloadMd() {{ download(`${{safeName()}}_checklist_entrada.md`, checklistMarkdown(), 'text/markdown'); }}
    async function checkBackend() {{
      const status = document.getElementById('backend-status');
      const storage = document.getElementById('storage-status');
      try {{
        const res = await fetch('/api/health', {{ cache: 'no-store' }});
        const data = await res.json();
        backendOnline = Boolean(data.ok);
        status.textContent = backendOnline ? 'Servicio: conectado' : 'Servicio: no disponible';
        status.className = backendOnline ? 'backend-status ok' : 'backend-status';
        storagePersistent = Boolean(data.storage?.persistent);
        storage.textContent = storagePersistent ? 'Archivos: almacenamiento permanente' : 'Archivos: descargue copias completas';
        storage.className = storagePersistent ? 'backend-status storage-status ok' : 'backend-status storage-status warn';
        document.getElementById('storage-metric').textContent = storagePersistent ? 'Permanente' : 'Con copias';
        if (backendOnline) await loadBackendProjects();
      }} catch (err) {{
        backendOnline = false;
        status.textContent = 'Servicio: modo navegador local';
        status.className = 'backend-status';
        storage.textContent = 'Archivos: sin verificar';
        document.getElementById('storage-metric').textContent = 'Sin verificar';
      }}
    }}
    async function createInBackend() {{
      const data = currentProject();
      if (!backendOnline) {{
        alert('Backend no conectado. Puede descargar la entrada JSON y cargarla despues en el motor.');
        return;
      }}
      const res = await fetch('/api/projects', {{
        method: 'POST',
        headers: apiHeaders(true),
        body: JSON.stringify(data)
      }});
      if (!res.ok) {{
        const errorText = await res.text();
        alert(`No se pudo crear el expediente: ${{errorText}}`);
        return;
      }}
      const created = await res.json();
      backendProjectId = created.project.project_id;
      const uploadInputs = Array.from(document.querySelectorAll('input[type=file]'));
      let uploadErrors = 0;
      for (const input of uploadInputs) {{
        const controlId = input.dataset.control;
        for (const file of Array.from(input.files || [])) {{
          const form = new FormData();
          form.append('control_id', controlId);
          form.append('file', file);
          const uploadResponse = await fetch(`/api/projects/${{encodeURIComponent(backendProjectId)}}/files`, {{
            method: 'POST',
            headers: apiHeaders(false),
            body: form
          }});
          if (!uploadResponse.ok) uploadErrors += 1;
        }}
      }}
      refresh();
      if (uploadErrors) {{
        alert(`Expediente guardado, pero ${{uploadErrors}} archivo(s) no pudieron subirse.`);
      }} else {{
        alert('Expediente y archivos guardados correctamente. Ahora pulse "Validar documentacion".');
      }}
      await validateInBackend();
      await loadBackendProjects();
    }}
    function renderGeneration(title, message, items = [], outputs = []) {{
      const box = document.getElementById('generation-box');
      const list = items.length ? `<ul>${{items.map((item) => `<li>${{item}}</li>`).join('')}}</ul>` : '';
      const files = outputs.length
        ? `<div class="actions">${{outputs.map((item, idx) => `<button class="secondary output-download" data-output="${{idx}}">${{item.label || 'Descargar'}}: ${{item.name}}</button>`).join('')}}</div>`
        : '';
      box.innerHTML = `<strong>${{title}}</strong><p class="muted">${{message || ''}}</p>${{list}}${{files}}`;
      outputs.forEach((item, idx) => {{
        box.querySelector(`[data-output="${{idx}}"]`)?.addEventListener('click', () => downloadOutput(item));
      }});
    }}
    async function validateInBackend() {{
      if (!backendProjectId) {{
        renderGeneration('Falta guardar el expediente', 'Pulse primero "Guardar expediente y subir archivos".');
        return false;
      }}
      const res = await fetch(`/api/projects/${{encodeURIComponent(backendProjectId)}}/readiness`, {{ headers: apiHeaders(false), cache: 'no-store' }});
      const body = await res.json();
      if (!res.ok) {{
        renderGeneration('No se pudo validar', body.error || 'Revise la clave de acceso.');
        return false;
      }}
      const readiness = body.readiness;
      document.getElementById('generate-document').disabled = !readiness.ready_for_generation;
      if (readiness.ready_for_generation) {{
        renderGeneration(
          'Documentacion minima completa',
          'Ya puede generar un borrador tecnico. El resultado seguira necesitando revision y auditoria final.'
        );
        return true;
      }}
      renderGeneration('Faltan datos o documentos', 'Complete estos elementos antes de generar:', readiness.blockers);
      return false;
    }}
    async function generateDocument() {{
      if (!(await validateInBackend())) return;
      document.getElementById('generate-document').disabled = true;
      renderGeneration('Generacion iniciada', 'Puede tardar varios minutos. Esta pagina mostrara el avance.');
      const res = await fetch(`/api/projects/${{encodeURIComponent(backendProjectId)}}/generate`, {{
        method: 'POST',
        headers: apiHeaders(false)
      }});
      const body = await res.json();
      if (!res.ok && body.generation?.status !== 'RUNNING') {{
        renderGeneration('No se pudo iniciar', body.generation?.readiness?.blockers?.join('. ') || body.error || 'Revise la documentacion.');
        return;
      }}
      pollGeneration();
    }}
    async function pollGeneration() {{
      if (!backendProjectId) return;
      const res = await fetch(`/api/projects/${{encodeURIComponent(backendProjectId)}}/generation-status`, {{
        headers: apiHeaders(false),
        cache: 'no-store'
      }});
      const body = await res.json();
      if (!res.ok) {{
        renderGeneration('No se pudo consultar el avance', body.error || '');
        return;
      }}
      const generation = body.generation;
      const stepItems = (generation.steps || []).map((step) => `${{step.status}}: ${{step.label}}`);
      renderGeneration(`Estado: ${{generation.status}}`, generation.message, stepItems, generation.outputs || []);
      if (generation.status === 'RUNNING') setTimeout(pollGeneration, 5000);
      else document.getElementById('generate-document').disabled = false;
    }}
    async function downloadOutput(item) {{
      const res = await fetch(item.download_url, {{ headers: apiHeaders(false) }});
      if (!res.ok) {{
        alert('No se pudo descargar el archivo.');
        return;
      }}
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = item.name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }}
    async function downloadBackup() {{
      if (!backendProjectId) {{
        alert('Guarde o abra primero un expediente.');
        return;
      }}
      const res = await fetch(`/api/projects/${{encodeURIComponent(backendProjectId)}}/backup`, {{
        headers: apiHeaders(false)
      }});
      if (!res.ok) {{
        alert('No se pudo crear la copia completa.');
        return;
      }}
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${{backendProjectId}}_COPIA_COMPLETA.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }}
    async function restoreBackup(file) {{
      if (!file) return;
      const form = new FormData();
      form.append('backup', file);
      const res = await fetch('/api/projects/restore', {{
        method: 'POST',
        headers: apiHeaders(false),
        body: form
      }});
      const body = await res.json();
      if (!res.ok) {{
        alert(`No se pudo restaurar la copia: ${{body.error || 'archivo no valido'}}`);
        return;
      }}
      backendProjectId = body.project.project_id;
      await loadBackendProjects();
      await loadBackendProject(backendProjectId);
      alert('Copia completa restaurada correctamente.');
    }}
    document.querySelectorAll('input, textarea, select').forEach((el) => el.addEventListener('input', refresh));
    document.querySelectorAll('input[type=file]').forEach((el) => el.addEventListener('change', refresh));
    document.getElementById('save-project').addEventListener('click', saveCurrent);
    document.getElementById('create-backend-bottom').addEventListener('click', createInBackend);
    document.getElementById('validate-backend').addEventListener('click', validateInBackend);
    document.getElementById('generate-document').addEventListener('click', generateDocument);
    document.getElementById('download-backup').addEventListener('click', downloadBackup);
    document.getElementById('restore-backup').addEventListener('click', () => document.getElementById('restore-backup-file').click());
    document.getElementById('restore-backup-file').addEventListener('change', (event) => restoreBackup(event.target.files?.[0]));
    document.getElementById('reset-form').addEventListener('click', () => {{
      document.querySelectorAll('input, textarea').forEach((el) => {{ if (el.type !== 'file') el.value = ''; }});
      document.querySelectorAll('select').forEach((el) => el.value = '');
      refresh();
    }});
    const accessKeyInput = document.getElementById('access-key');
    accessKeyInput.value = localStorage.getItem(accessKeyStorage) || '';
    accessKeyInput.addEventListener('input', () => localStorage.setItem(accessKeyStorage, accessKeyInput.value));
    accessKeyInput.addEventListener('change', loadBackendProjects);
    renderProjects();
    refresh();
    checkBackend();
  </script>
</body>
</html>
"""
