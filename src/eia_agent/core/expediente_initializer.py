"""
expediente_initializer.py — BE-03
Inicializador de estructura estandar de expediente EIA-Agent v2.1.

Crea la jerarquia de carpetas, archivos guia y metadatos minimos para
un expediente nuevo, sin ejecutar pipeline ni generar informe ambiental.

No llama a IA, web ni APIs externas.
administrative_ready siempre False.
"""
from __future__ import annotations

import json
import re
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

STANDARD_EXPEDIENTE_DIRS: list[str] = [
    "inputs",
    "inputs/memoria_tecnica",
    "inputs/memoria_explotacion",
    "inputs/fotos",
    "inputs/imagenes",
    "inputs/cartografia_aportada",
    "control_interno",
    "fase1",
    "fase2",
    "fase3",
    "fase4",
    "inventario",
    "impactos",
    "auditoria",
    "documento",
    "documento/figuras",
    "cartografia",
    "cartografia/mapas",
    "clima",
    "logs",
]

STANDARD_GUIDE_FILES: list[str] = [
    "README_EXPEDIENTE.md",
    "inputs/INSTRUCCIONES_INPUTS.md",
    "control_interno/ESTADO_EXPEDIENTE.md",
    "control_interno/PENDIENTES_PROMOTOR.md",
    "documento/README_DOCUMENTO.md",
]

STANDARD_METADATA_FILE: str = "control_interno/expediente_metadata.json"

STATUS_VALUES: dict[str, str] = {
    "CREATED": "CREATED",
    "UPDATED": "UPDATED",
    "ALREADY_EXISTS": "ALREADY_EXISTS",
    "ERROR": "ERROR",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ExpedienteInitFile:
    """Resultado de creacion/omision de un archivo guia."""
    path: str
    created: bool = False
    overwritten: bool = False
    skipped: bool = False
    file_size_bytes: int = 0
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "created": self.created,
            "overwritten": self.overwritten,
            "skipped": self.skipped,
            "file_size_bytes": self.file_size_bytes,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        if self.skipped:
            return f"[SKIPPED] {self.path}"
        if self.overwritten:
            return f"[OVERWRITTEN] {self.path} ({self.file_size_bytes} bytes)"
        if self.created:
            return f"[CREATED] {self.path} ({self.file_size_bytes} bytes)"
        return f"[?] {self.path}"


@dataclass
class ExpedienteInitResult:
    """Resultado completo de la inicializacion de un expediente."""
    expediente_id: str
    expediente_path: str
    status: str
    dirs_created: list[str] = field(default_factory=list)
    dirs_existing: list[str] = field(default_factory=list)
    files: list[ExpedienteInitFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def created_dir_count(self) -> int:
        return len(self.dirs_created)

    def existing_dir_count(self) -> int:
        return len(self.dirs_existing)

    def created_file_count(self) -> int:
        return sum(1 for f in self.files if f.created or f.overwritten)

    def skipped_file_count(self) -> int:
        return sum(1 for f in self.files if f.skipped)

    def is_success(self) -> bool:
        return self.status != STATUS_VALUES["ERROR"]

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "expediente_path": self.expediente_path,
            "status": self.status,
            "dirs_created": list(self.dirs_created),
            "dirs_existing": list(self.dirs_existing),
            "files": [f.to_dict() for f in self.files],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "stats": {
                "dirs_created": self.created_dir_count(),
                "dirs_existing": self.existing_dir_count(),
                "files_created": self.created_file_count(),
                "files_skipped": self.skipped_file_count(),
            },
        }

    def summary(self) -> str:
        lines = [
            f"Expediente   : {self.expediente_id}",
            f"Ruta         : {self.expediente_path}",
            f"Estado       : {self.status}",
            f"Carpetas     : {self.created_dir_count()} creadas, {self.existing_dir_count()} existentes",
            f"Archivos     : {self.created_file_count()} creados/actualizados, "
            f"{self.skipped_file_count()} omitidos",
        ]
        if self.warnings:
            lines.append(f"Avisos       : {len(self.warnings)}")
            for w in self.warnings[:5]:
                lines.append(f"  [AVISO] {w}")
        for n in self.notes[:3]:
            lines.append(f"  [NOTA] {n}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def sanitize_expediente_id(value: str) -> str:
    """Limpia un string para usarlo como identificador de expediente.

    - Sustituye espacios, barras y otros separadores por guion medio
    - Elimina caracteres no alfanumericos salvo guion y guion bajo
    - Colapsa guiones consecutivos
    - Convierte a mayusculas
    """
    if not value:
        return ""
    result = re.sub(r"[\s/\\:;,\.]+", "-", value)
    result = re.sub(r"[^A-Za-z0-9_\-]", "", result)
    result = re.sub(r"-{2,}", "-", result)
    result = result.strip("-_")
    return result.upper()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_default_metadata(expediente_id: str) -> dict:
    """Devuelve el JSON minimo de metadatos para un expediente nuevo.

    administrative_ready siempre False.
    """
    return {
        "expediente_id": expediente_id,
        "created_at": _now_iso(),
        "tool": "EIA-Agent v2.1",
        "status": "CREATED",
        "administrative_ready": False,
        "notes": [
            "Expediente inicializado automaticamente.",
            "Este expediente no declara aptitud administrativa.",
        ],
    }


def build_readme_expediente(expediente_id: str) -> str:
    """Genera README_EXPEDIENTE.md con estructura, flujo y advertencia de alcance."""
    return f"""# Expediente EIA-Agent — {expediente_id}

## 1. Identificacion

- **ID del expediente:** {expediente_id}
- **Herramienta:** EIA-Agent v2.1
- **Tipo:** Documento Ambiental para Evaluacion de Impacto Ambiental simplificada

## 2. Estructura de carpetas

```
{expediente_id}/
├── inputs/                     → Documentos aportados por el promotor
│   ├── memoria_tecnica/        → Memoria tecnica del proyecto
│   ├── memoria_explotacion/    → Memoria de explotacion / operaciones
│   ├── fotos/                  → Fotografias del emplazamiento
│   ├── imagenes/               → Planos, esquemas, diagramas
│   └── cartografia_aportada/   → Cartografia aportada por el promotor
├── control_interno/            → Logs, checkpoints, metadatos, auditoria
├── fase1/                      → Outputs de Fase 1 (ingesta)
├── fase2/                      → Outputs de Fase 2 (cierre del objeto)
├── fase3/                      → Outputs de Fase 3 (triaje normativo)
├── fase4/                      → Outputs de Fase 4 (cartografia y clima)
├── inventario/                 → Fichas de inventario ambiental (Fase 5)
├── impactos/                   → Matrices de impactos, medidas y PVA (Fase 6)
├── auditoria/                  → Resultados de auditoria programatica
├── documento/                  → Documento Ambiental borrador y paquete final
│   └── figuras/               → Figuras y anexos graficos adicionales
├── cartografia/                → Plan cartografico y mapas generados
│   └── mapas/                 → Archivos PNG de mapas
├── clima/                      → Datos climaticos y climograma
└── logs/                       → Logs de ejecucion
```

## 3. Inputs necesarios

Deposite los documentos del promotor en la carpeta `inputs/` segun su tipo:

- **Memoria tecnica** → `inputs/memoria_tecnica/`
- **Memoria de explotacion** → `inputs/memoria_explotacion/`
- **Fotografias** → `inputs/fotos/`
- **Planos e imagenes** → `inputs/imagenes/`
- **Cartografia aportada** → `inputs/cartografia_aportada/`

Consulte `inputs/INSTRUCCIONES_INPUTS.md` para los datos minimos requeridos.

## 4. Flujo recomendado

1. Depositar inputs del promotor en `inputs/`
2. `phase1 --write` — indexar y extraer entidades
3. `phase2 --write` — cerrar el objeto evaluado (gate critico)
4. `phase3 --write` — triaje normativo
5. `phase4-offline --write` — cartografia y clima
6. `inventory-build --write` + `inventory-gate --write` — inventario ambiental
7. `run-technical-pipeline --write` — impactos, medidas, PVA, auditoria completa
8. `document-manifest --write` + `document-build-md --write` + `document-build-docx --write`
9. `document-package --write` + `document-export --write`
10. `document-prepare-presentation --write` — preparar para revision y firmas

## 5. Comandos principales

```bash
python run_expediente.py {expediente_id} status
python run_expediente.py {expediente_id} phase1 --write
python run_expediente.py {expediente_id} run-technical-pipeline --write
python run_expediente.py {expediente_id} document-manifest --write
```

## 6. Advertencia de alcance

> **IMPORTANTE:** Este expediente no declara aptitud administrativa.
> El Documento Ambiental generado por EIA-Agent v2.1 requiere revision tecnica
> y juridica antes de cualquier presentacion ante la administracion.
> El promotor es responsable de la veracidad de los datos aportados.
> EIA-Agent v2.1 opera en modo gabinete: los datos de campo deben ser aportados
> por el promotor o por tecnicos habilitados.
"""


def build_inputs_instructions() -> str:
    """Genera inputs/INSTRUCCIONES_INPUTS.md con datos minimos requeridos."""
    return """# Instrucciones para depositar inputs del promotor

## Carpetas disponibles

| Carpeta | Contenido esperado |
|---------|-------------------|
| `inputs/memoria_tecnica/` | Memoria tecnica del proyecto (DOCX, PDF) |
| `inputs/memoria_explotacion/` | Descripcion de actividades, operaciones, maquinaria, residuos, horarios |
| `inputs/fotos/` | Fotografias del emplazamiento (JPG, PNG) |
| `inputs/imagenes/` | Planos, esquemas, diagramas de proceso (JPG, PNG, PDF) |
| `inputs/cartografia_aportada/` | Cartografia aportada por el promotor (SHP, KMZ, PDF, PNG) |

## Datos minimos necesarios

### Datos de identificacion
- **Promotor:** nombre o razon social del titular
- **Actividad:** tipo de actividad principal (con codigo CNAE si disponible)
- **Ubicacion:** municipio, isla (para Canarias), direccion

### Datos catastrales y de localizacion
- **Coordenadas:** latitud y longitud (WGS84) o UTM 28N del emplazamiento
- **Referencia catastral:** si existe (formato de 20 caracteres del Catastro)

### Descripcion tecnica
- **Descripcion de operaciones:** secuencia de actividades del proceso productivo
- **Maquinaria:** lista de equipos y maquinaria (con potencia si es relevante)
- **Residuos:** tipos de residuos generados o gestionados (con codigo LER si conocido)
- **Operaciones de gestion de residuos:** codigos R/D aplicables (R12, R13, D15, etc.)

### Datos operativos
- **Horarios:** horario de funcionamiento previsto
- **Capacidad:** capacidad de tratamiento o almacenamiento (toneladas/anio, m3, etc.)

### Medidas ambientales existentes
- Medidas o instalaciones de proteccion ambiental ya presentes o proyectadas

## Formatos admitidos

- Documentos de texto: DOCX (preferido), PDF
- Imagenes y mapas: JPG, PNG, PDF
- Datos tabulares: XLSX, CSV
- Cartografia: SHP (con archivos asociados), KMZ, KML, GeoJSON

## Nota sobre privacidad

Los archivos depositados en `inputs/` no son enviados a ningun servicio externo.
EIA-Agent v2.1 opera completamente en modo local (sin IA online, sin web).
"""


def build_estado_expediente_template(expediente_id: str) -> str:
    """Genera control_interno/ESTADO_EXPEDIENTE.md con checklist inicial."""
    return f"""# Estado del expediente — {expediente_id}

**Actualizado:** (pendiente de ejecucion)

## Checklist de progreso

| Fase | Estado | Fecha | Observaciones |
|------|--------|-------|---------------|
| Inputs recibidos | Pendiente | — | Depositar en `inputs/` |
| Fase 1 ejecutada | Pendiente | — | `phase1 --write` |
| Fase 2 ejecutada | Pendiente | — | `phase2 --write` (gate critico) |
| Fase 3 ejecutada | Pendiente | — | `phase3 --write` |
| Fase 4 ejecutada | Pendiente | — | `phase4-offline --write` |
| Inventario generado | Pendiente | — | `inventory-build --write` |
| Gate Fase 5 | Pendiente | — | `inventory-gate --write` |
| Pipeline tecnico (Fase 6 + Auditoria) | Pendiente | — | `run-technical-pipeline --write` |
| Documento generado | Pendiente | — | `document-build-md --write` + `document-build-docx --write` |
| Paquete preparado | Pendiente | — | `document-package --write` |
| Exportacion ZIP | Pendiente | — | `document-export --write` |
| Preparacion para presentacion | Pendiente | — | `document-prepare-presentation --write` |

## Pendientes criticos

(Sin pendientes registrados — actualizar a medida que avance el expediente)

## Notas

- Este archivo es de seguimiento manual. Actualizar segun avance del expediente.
- El estado definitivo de auditoria esta en `auditoria/final_audit_result.json`.
- `administrative_ready` siempre es False hasta presentacion administrativa validada.
"""


def build_pendientes_promotor_template() -> str:
    """Genera control_interno/PENDIENTES_PROMOTOR.md con tabla de pendientes."""
    return """# Pendientes del promotor — EIA-Agent v2.1

## Tabla de pendientes

| Prioridad | Dato pendiente | Motivo | Estado |
|-----------|---------------|--------|--------|
| ALTA | (sin pendientes registrados) | — | — |

## Instrucciones

- **ALTA:** bloquea el avance. No se puede continuar sin este dato.
- **MEDIA:** necesario para completar el expediente pero no bloquea inmediatamente.
- **BAJA:** mejora la calidad pero no es imprescindible.

Actualizar esta tabla a medida que se identifiquen gaps durante el analisis.
"""


def build_documento_readme() -> str:
    """Genera documento/README_DOCUMENTO.md con descripcion de outputs documentales."""
    return """# Carpeta documento/ — EIA-Agent v2.1

Esta carpeta contiene el Documento Ambiental generado y todos los archivos
necesarios para la entrega final.

## Archivos generados por la cadena documental

| Archivo | Descripcion | Comando |
|---------|-------------|---------|
| `document_manifest.json` | Estado de todos los bloques A-K | `document-manifest --write` |
| `document_manifest.md` | Resumen legible del manifest | `document-manifest --write` |
| `documento_ambiental_borrador.md` | Borrador Markdown del DA completo | `document-build-md --write` |
| `document_build_result.json` | Resultado del generador Markdown | `document-build-md --write` |
| `documento_ambiental_borrador.docx` | Borrador DOCX sin figuras | `document-build-docx --write` |
| `docx_build_result.json` | Resultado del generador DOCX | `document-build-docx --write` |
| `documento_ambiental_borrador_con_figuras.docx` | DOCX con anexo grafico | `document-insert-figures --write` |
| `document_figures_result.json` | Resultado de insercion de figuras | `document-insert-figures --write` |
| `document_quality_result.json` | Resultado del control de calidad | `document-qc --write` |
| `paquete_entrega/` | Paquete estructurado para entrega | `document-package --write` |
| `paquete_entrega.zip` | ZIP del paquete de entrega | `document-export --write` |
| `documento_ambiental_final_revisable.docx` | DOCX final con hoja de firmas | `document-prepare-presentation --write` |

## Subcarpetas

- `figuras/` — figuras adicionales (fotografias, esquemas) para el anexo grafico
- `paquete_entrega/` — paquete estructurado con 4 secciones para entrega

## Notas

- El DOCX generado NO esta listo para presentacion administrativa directa.
- Requiere revision tecnica y juridica antes de cualquier presentacion.
- `administrative_ready` es siempre `False` en todos los outputs.
"""


# ---------------------------------------------------------------------------
# Funciones de creacion
# ---------------------------------------------------------------------------

def create_standard_dirs(
    expediente_path: "str | Path",
) -> "tuple[list[str], list[str]]":
    """Crea la estructura estandar de carpetas del expediente.

    Returns:
        (dirs_created, dirs_existing)
    """
    exp_path = Path(expediente_path)
    dirs_created: list[str] = []
    dirs_existing: list[str] = []

    for rel_dir in STANDARD_EXPEDIENTE_DIRS:
        target = exp_path / rel_dir
        if target.exists():
            dirs_existing.append(rel_dir)
        else:
            target.mkdir(parents=True, exist_ok=True)
            dirs_created.append(rel_dir)

    return dirs_created, dirs_existing


def write_standard_guides(
    expediente_path: "str | Path",
    expediente_id: str,
    force: bool = False,
) -> "list[ExpedienteInitFile]":
    """Escribe los archivos guia estandar y el metadata JSON.

    Si force=False: omite archivos existentes (skipped=True).
    Si force=True: sobrescribe archivos guia (overwritten=True).
    Nunca borra archivos que no sean de esta lista.
    """
    exp_path = Path(expediente_path)

    guide_content: dict[str, str] = {
        "README_EXPEDIENTE.md": build_readme_expediente(expediente_id),
        "inputs/INSTRUCCIONES_INPUTS.md": build_inputs_instructions(),
        "control_interno/ESTADO_EXPEDIENTE.md": build_estado_expediente_template(expediente_id),
        "control_interno/PENDIENTES_PROMOTOR.md": build_pendientes_promotor_template(),
        "documento/README_DOCUMENTO.md": build_documento_readme(),
    }

    results: list[ExpedienteInitFile] = []

    for rel_path, content in guide_content.items():
        target = exp_path / rel_path
        init_file = ExpedienteInitFile(path=rel_path)

        if target.exists() and not force:
            init_file.skipped = True
            init_file.file_size_bytes = target.stat().st_size
            results.append(init_file)
            continue

        was_existing = target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        size = target.stat().st_size

        init_file.overwritten = was_existing
        init_file.created = not was_existing
        init_file.file_size_bytes = size
        results.append(init_file)

    # Metadata JSON
    metadata_rel = STANDARD_METADATA_FILE
    metadata_path = exp_path / metadata_rel
    meta_file = ExpedienteInitFile(path=metadata_rel)

    if metadata_path.exists() and not force:
        meta_file.skipped = True
        meta_file.file_size_bytes = metadata_path.stat().st_size
    else:
        was_existing = metadata_path.exists()
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = build_default_metadata(expediente_id)
        if was_existing:
            try:
                existing = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata["created_at"] = existing.get("created_at", metadata["created_at"])
                metadata["status"] = "UPDATED"
            except Exception:
                pass
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        size = metadata_path.stat().st_size
        meta_file.overwritten = was_existing
        meta_file.created = not was_existing
        meta_file.file_size_bytes = size

    results.append(meta_file)
    return results


def initialize_expediente(
    base_path: "str | Path",
    expediente_id: "str | None" = None,
    force: bool = False,
    with_guides: bool = True,
) -> ExpedienteInitResult:
    """Inicializa la estructura estandar de un expediente EIA-Agent.

    Args:
        base_path: Ruta al directorio del expediente (se crea si no existe).
        expediente_id: ID del expediente. Si None, usa el nombre de base_path sanitizado.
        force: Si True, sobrescribe archivos guia existentes.
        with_guides: Si False, solo crea la estructura de carpetas.

    Returns:
        ExpedienteInitResult con el resultado completo.
    """
    exp_path = Path(base_path).resolve()

    if expediente_id is None or not expediente_id.strip():
        eid = sanitize_expediente_id(exp_path.name)
    else:
        eid = sanitize_expediente_id(expediente_id)
        if not eid:
            eid = sanitize_expediente_id(exp_path.name)

    root_existed = exp_path.exists()
    status = "ALREADY_EXISTS" if root_existed else "CREATED"

    try:
        exp_path.mkdir(parents=True, exist_ok=True)

        dirs_created, dirs_existing = create_standard_dirs(exp_path)

        files: list[ExpedienteInitFile] = []
        if with_guides:
            files = write_standard_guides(exp_path, eid, force=force)

        notes: list[str] = [
            f"Estructura inicializada para expediente {eid}.",
            "Este expediente no declara aptitud administrativa.",
        ]
        if root_existed and not force:
            notes.append(
                "El directorio raiz ya existia. Se han respetado los archivos existentes."
            )

        return ExpedienteInitResult(
            expediente_id=eid,
            expediente_path=str(exp_path),
            status=status,
            dirs_created=dirs_created,
            dirs_existing=dirs_existing,
            files=files,
            warnings=[],
            notes=notes,
        )

    except Exception as exc:
        return ExpedienteInitResult(
            expediente_id=eid,
            expediente_path=str(exp_path),
            status="ERROR",
            warnings=[f"Error inicializando expediente: {exc}"],
            notes=[traceback.format_exc()[-300:]],
        )


def write_init_result(
    result: ExpedienteInitResult,
    output_path: "str | Path",
) -> Path:
    """Escribe el resultado de inicializacion en JSON.

    Args:
        result: Resultado de initialize_expediente.
        output_path: Ruta del archivo JSON de salida.

    Returns:
        Path al archivo escrito.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out
