# DOCUMENT_PACKAGE_BUILDER.md — DOC-06

## Que hace DOC-06

DOC-06 es el empaquetador final del Documento Ambiental. Su funcion es recopilar y
organizar los outputs documentales y de auditoria ya generados (DOC-00 a DOC-05)
en una carpeta estructurada `documento/paquete_entrega/` lista para revision tecnica.

## Que NO hace DOC-06

- **No genera PDF.** El paquete incluye DOCX y Markdown, no PDF.
- **No genera ZIP.** Los archivos se copian sueltos; la compresion es tarea de DOC-07.
- **No corrige documentos.** Si un bloque tiene errores, el paquete los refleja tal cual.
- **No declara aptitud administrativa.** El paquete de entrega es un borrador de trabajo.
  La presentacion administrativa requiere revision tecnica/juridica por tecnico competente.
- **No modifica DOCX, Markdown ni ningun archivo fuente.**
- **No usa IA, no consulta APIs externas, no llama a servicios web.**

## Estructura del paquete de entrega

```
documento/paquete_entrega/
├── 01_documento_ambiental/
│   ├── documento_ambiental_borrador_con_figuras.docx  (si existe)
│   ├── documento_ambiental_borrador.docx
│   └── documento_ambiental_borrador.md
├── 02_auditorias/
│   ├── final_audit_result.md
│   ├── final_audit_result.json
│   ├── document_quality_result.md
│   ├── document_quality_result.json
│   ├── conditional_chain_result.json  (IM-09, si existe)
│   ├── conditional_chain_result.md    (IM-09, si existe)
│   └── demas auditorias disponibles (art45, prudence, traceability, etc.)
├── 03_anexos_graficos/
│   └── document_figures_result.md
└── 04_trazabilidad/
    ├── document_manifest.md
    ├── document_manifest.json
    ├── document_build_result.json
    ├── docx_build_result.json
    └── document_figures_result.json
```

Tambien genera en `documento/`:
- `package_build_result.json`
- `package_build_result.md`

## Archivos requeridos y opcionales

### Requeridos (su ausencia marca is_success=False)

| Archivo | Descripcion |
|---------|-------------|
| `documento/documento_ambiental_borrador.docx` | DOCX base (DOC-02) |
| `documento/documento_ambiental_borrador.md` | Markdown base (DOC-01) |

### Opcionales (su ausencia genera WARNING pero no ERROR)

| Archivo | Descripcion |
|---------|-------------|
| `documento/documento_ambiental_borrador_con_figuras.docx` | DOCX enriquecido (DOC-03) |
| `auditoria/final_audit_result.json` / `.md` | Auditoria final (AU-04) |
| `documento/document_quality_result.json` / `.md` | QC documental (DOC-04) |
| `auditoria/art45_checklist_result.json` | Checklist art. 45 (AU-01) |
| `auditoria/prudence_validation_result.json` | Validador prudencia (AU-02) |
| `auditoria/traceability_validation_result.json` | Trazabilidad (AU-03) |
| `auditoria/block_consistency_result.json` | Coherencia bloques (RD-04) |
| `auditoria/conesa_check_result.json` | Cobertura Conesa (RD-06) |
| `auditoria/diagnostic_measure_validation_result.json` | Medidas diagnosticas (RD-08) |
| `auditoria/prl_measure_validation_result.json` | Medidas PRL (RD-09) |
| `auditoria/conditional_chain_result.json` / `.md` | Cadenas condicionales IM-09 (DOC-09) |
| `documento/document_manifest.json` / `.md` | Manifest (DOC-00) |
| `documento/document_build_result.json` | Resultado build MD (DOC-01) |
| `documento/docx_build_result.json` | Resultado build DOCX (DOC-02) |
| `documento/document_figures_result.json` / `.md` | Resultado figuras (DOC-03) |

### Regla DOCX enriquecido

Si `document_figures_result.json` indica `generated=True` pero el DOCX enriquecido
no existe, se emite un WARNING. El paquete se puede generar de forma parcial con el
DOCX base si el DOCX enriquecido no esta disponible.

## Como usar la CLI

### Ver que se empaquetaria (sin escribir nada)

```bash
python run_expediente.py <expediente> document-package
```

Muestra un resumen de archivos disponibles y faltantes. No crea ninguna carpeta.
Exit 0 si los requeridos estan presentes; exit 1 si faltan requeridos.

### Generar el paquete

```bash
python run_expediente.py <expediente> document-package --write
```

Crea `documento/paquete_entrega/`, copia los archivos, genera README_ENTREGA.md y
los archivos de resultado. Exit 0 si es_success(); exit 1 si faltan requeridos.

### Opciones

| Opcion | Descripcion |
|--------|-------------|
| `--write` | Copiar archivos y generar paquete (por defecto solo muestra) |
| `--overwrite` | Sobreescribir paquete_entrega/ si ya existe (comportamiento por defecto) |

## API Python

```python
from eia_agent.core.document_package_builder import (
    build_document_package,
    write_package_build_outputs,
    collect_package_files,
    PackageFile,
    DocumentPackageResult,
)

# Analizar sin escribir
result = build_document_package(exp_path, write_outputs=False)
print(result.summary())
print("Requeridos faltantes:", result.required_missing)

# Generar paquete
result = build_document_package(exp_path, write_outputs=True, overwrite=True)
if result.is_success():
    doc_dir = exp_path / "documento"
    json_path, md_path = write_package_build_outputs(result, doc_dir)
```

## Como ejecutar los tests

```bash
# Solo DOC-06
venv\Scripts\python -m unittest tests.test_document_package_builder

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```

## Siguiente paso sugerido

- **DOC-07** — Generacion de ZIP o export final del paquete de entrega.
- **QA-07** — Prueba real del paquete de entrega sobre expediente NAVE-222.
