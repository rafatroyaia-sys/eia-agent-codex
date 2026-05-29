# EXPEDIENTE_INITIALIZER — BE-03

## Qué hace

`expediente_initializer.py` crea la estructura de carpetas y archivos guía estándar
para un nuevo expediente EIA-Agent, de forma determinista y sin dependencias externas.

A partir de un `base_path` (carpeta donde vivirá el expediente) y un `expediente_id`
opcional, el módulo:

1. Crea la carpeta raíz `<base_path>/<expediente_id>/` si no existe.
2. Crea las 20 subcarpetas estándar del expediente.
3. Escribe los 5 archivos guía markdown (salvo que `with_guides=False`).
4. Escribe el archivo de metadatos `control_interno/expediente_metadata.json`.
5. Devuelve un `ExpedienteInitResult` con el detalle de todo lo creado.

## Qué NO hace

- **No ejecuta el pipeline EIA-Agent** (fases 1-9, AG-X, M-X).
- **No interpreta ni parsea documentos** del promotor.
- **No genera ningún bloque, sección ni informe ambiental**.
- **No declara aptitud administrativa**: el campo `administrative_ready` siempre es `False`.
- **No modifica expedientes existentes** salvo los archivos guía cuando `force=True`.
- **No borra archivos**: si el expediente ya tiene contenido, lo respeta.
- **No llama a APIs, servicios web ni IA**.

## Estructura estándar creada

```
<expediente_id>/
├── inputs/
│   ├── memorias_tecnicas/
│   ├── planos/
│   └── otras_aportaciones/
├── cartografia/
│   ├── capas/
│   └── mapas/
├── clima/
├── fichas_inventario/
├── impactos/
├── bloques/
├── documento/
│   └── figuras/
├── anejos/
├── control_interno/
└── output/
    ├── zip/
    └── pdf/
```

Total: **20 directorios**.

## Archivos guía

| Archivo | Propósito |
|---------|-----------|
| `README_EXPEDIENTE.md` | Descripción del expediente, estructura, flujo de fases y advertencias |
| `INSTRUCCIONES_INPUTS.md` | Datos mínimos que debe aportar el promotor |
| `ESTADO_EXPEDIENTE.md` | Checklist de 12 ítems para seguimiento de avance |
| `PENDIENTES_PROMOTOR.md` | Tabla de pendientes con prioridad ALTA / MEDIA / BAJA |
| `documento/README_DOCUMENTO.md` | Descripción de los outputs documentales generados |

Más el metadata:

| Archivo | Propósito |
|---------|-----------|
| `control_interno/expediente_metadata.json` | ID, ruta, timestamps, estado, herramienta, advertencias |

Los archivos guía no se sobreescriben en segunda ejecución salvo `--force`.

## ID del expediente

Si no se pasa `expediente_id`, se usa el nombre de la carpeta `base_path` como ID.

El ID se sanitiza automáticamente:
- Espacios → guiones
- Todo en mayúsculas
- Se eliminan caracteres especiales excepto guiones

Ejemplos:
```
"Recimetal Nave 222"  →  "RECIMETAL-NAVE-222"
"EIA 2026/prueba"     →  "EIA-2026-PRUEBA"
"nave_222"            →  "NAVE-222"
```

## Uso CLI

```
python run_expediente.py <ruta_expediente> init-expediente [--force] [--no-guides]
```

### Argumentos

| Argumento | Descripción |
|-----------|-------------|
| `<ruta_expediente>` | Ruta al expediente (puede no existir aún) |
| `init-expediente` | Subcomando de inicialización |
| `--force` | Sobreescribir archivos guía si ya existen |
| `--no-guides` | Crear solo carpetas, sin archivos guía ni metadata |

### Ejemplos

Crear un expediente nuevo desde cero:
```
python run_expediente.py expedientes/EIA-2026-NAVE-123 init-expediente
```

Recrear archivos guía sobre un expediente existente:
```
python run_expediente.py expedientes/EIA-2026-NAVE-123 init-expediente --force
```

Solo carpetas, sin guías:
```
python run_expediente.py expedientes/EIA-2026-NAVE-123 init-expediente --no-guides
```

El resultado se escribe en `control_interno/init_expediente_result.json`.

## API Python

```python
from eia_agent.core.expediente_initializer import initialize_expediente

result = initialize_expediente(
    base_path="expedientes/EIA-2026-NAVE-123",
    expediente_id=None,   # usa el nombre de la carpeta si es None
    force=False,
    with_guides=True,
)

print(result.summary())
print(result.is_success())       # True / False
print(result.created_dir_count())
print(result.created_file_count())
```

### Tipos de retorno

**`ExpedienteInitResult`**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `expediente_id` | str | ID sanitizado |
| `expediente_path` | Path | Ruta absoluta a la carpeta raíz |
| `status` | str | "CREATED" o "ERROR" |
| `dirs_created` | list[str] | Carpetas creadas en esta ejecución |
| `dirs_existing` | list[str] | Carpetas que ya existían |
| `files` | list[ExpedienteInitFile] | Detalle por archivo |
| `warnings` | list[str] | Avisos no bloqueantes |
| `notes` | list[str] | Notas informativas |

**`ExpedienteInitFile`**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `path` | str | Ruta relativa dentro del expediente |
| `created` | bool | True si se creó en esta ejecución |
| `overwritten` | bool | True si se sobreescribió (force=True) |
| `skipped` | bool | True si se omitió (existía, force=False) |
| `file_size_bytes` | int | Tamaño en bytes |
| `warnings` | list[str] | Avisos específicos del archivo |
| `notes` | list[str] | Notas del archivo |

## Cómo ejecutar los tests

```
venv\Scripts\python -m unittest tests.test_expediente_initializer
```

Suite completa (94 tests):
- `TestSanitizeExpedienteId` — 15 tests
- `TestBuildDefaultMetadata` — 7 tests
- `TestBuildersMarkdown` — 16 tests
- `TestCreateStandardDirs` — 5 tests
- `TestWriteStandardGuides` — 7 tests
- `TestInitializeExpediente` — 14 tests
- `TestWriteInitResult` — 4 tests
- `TestDataclasses` — 12 tests
- `TestCLIInitExpediente` — 6 tests
- `TestConstantes` — 8 tests

Todos los tests usan `tempfile.TemporaryDirectory` — no modifican expedientes piloto.

## Relación con RELEASE-01

BE-03 es el primer módulo de la capa de almacenamiento (BE-layer).
No depende de RELEASE-01 ni del pipeline de fases.

RELEASE-01 usará BE-03 para garantizar que cualquier expediente nuevo parte de
la estructura canónica antes de ejecutar las fases AG-X y M-X.

## Constantes exportadas

| Constante | Descripción |
|-----------|-------------|
| `STANDARD_EXPEDIENTE_DIRS` | Lista de 20 directorios estándar |
| `STANDARD_GUIDE_FILES` | Diccionario de 5 archivos guía (nombre → builder) |
| `STANDARD_METADATA_FILE` | Ruta relativa del metadata JSON |
| `STATUS_VALUES` | Valores válidos de estado: CREATED, UPDATED, ALREADY_EXISTS, ERROR |
