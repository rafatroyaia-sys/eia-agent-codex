# CONFIG_MANAGER — BE-04

## Qué hace

`config_manager.py` gestiona de forma segura la configuración local y las API keys
de EIA-Agent v2.1. Proporciona:

1. **Documentación de variables** conocidas (`KNOWN_ENV_VARS`).
2. **Validación offline** — detecta variables ausentes, placeholders y valores inválidos
   sin llamar a ningún servicio externo.
3. **Detección de secretos** — escanea archivos del repositorio buscando patrones
   sospechosos (tokens JWT, claves `sk-...`, tokens Mapbox, etc.).
4. **Informe seguro** — nunca imprime claves reales; los valores sensibles aparecen
   siempre enmascarados (`abcd...wxyz`).
5. **Integración con el CLI** — comandos `config-check` y `secrets-scan`.

## Qué NO hace

- **No valida claves contra APIs externas** — no comprueba si `AEMET_API_KEY` es
  correcta llamando a AEMET.
- **No llama a servicios externos** — todo el procesamiento es offline.
- **No almacena secretos** — los valores reales nunca se guardan en disco.
- **No muestra claves reales** — ni en pantalla, ni en JSON, ni en Markdown.
- **No modifica expedientes piloto** ni ningún documento ambiental.

## Variables soportadas

| Variable | Sensible | Obligatoria | Descripción |
|----------|----------|-------------|-------------|
| `AEMET_API_KEY` | Sí | No (Fase 4 online) | API key para AEMET OpenData |
| `MAPBOX_TOKEN` | Sí | No (Fase 4 online) | Token para mapas base Mapbox |
| `OPENAI_API_KEY` | Sí | No (nunca en pipeline offline) | Clave OpenAI si se usa GPT como fallback |
| `EIA_ENV` | No | No | Entorno de ejecución |

### Valores válidos de EIA_ENV

`local`, `dev`, `ci`, `test`, `prod`

Un valor fuera de este rango genera un aviso `BE04-W003`.

## Uso de .env y .env.example

### Configuración rápida

```
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Edita `.env` con tus claves reales. Este archivo **nunca debe subirse a git**
(está en `.gitignore`).

### Prioridad de lectura

1. Variables de entorno del sistema operativo (`os.environ`)
2. Archivo `.env` en la raíz del proyecto o expediente

### .env.example

Solo contiene valores vacíos o comentarios. Es el único archivo `.env` versionado.

## Comando: config-check

```
python run_expediente.py <expediente> config-check [--write]
```

Valida las variables de entorno conocidas:

- Lee `.env` si existe en la raíz del proyecto o expediente.
- Detecta ausencias, placeholders y valores inválidos.
- **Sin `--write`**: solo imprime resumen en pantalla.
- **Con `--write`**: escribe `control_interno/config_validation_result.json`
  y `control_interno/config_validation_result.md`.
- **Exit 0** si `is_valid()` (sin ERRORs).
- **Exit 1** si hay algún ERROR.

### Ejemplo de salida

```
Config  : CON_OBSERVACIONES
Vars    : 4 revisadas, 1 presentes
Errores : 0
Avisos  : 1
Info    : 3
```

## Comando: secrets-scan

```
python run_expediente.py <expediente> secrets-scan [--write]
```

Escanea archivos del repositorio en busca de patrones de secretos:

- Analiza: `.py`, `.md`, `.json`, `.yml`, `.yaml`, `.txt`, `.sh`, `.bat`, etc.
- Excluye: `.git/`, `venv/`, `tmp/`, `__pycache__/`, `.pytest_cache/`, `expediente-EIA-*/`.
- **Nunca imprime valores completos** — solo fragmentos enmascarados.
- **Con `--write`**: escribe informe en `control_interno/`.
- **Exit 0** si no se detectan secretos.
- **Exit 1** si se detectan secretos potenciales (código `BE04-E003`).

### Patrones detectados

| Patrón | Descripción |
|--------|-------------|
| `sk-[20+ chars]` | Posible clave OpenAI |
| `pk.[20+ chars]` | Posible token Mapbox public |
| `sk.[20+ chars]` | Posible token Mapbox secret |
| `xxx.yyy.zzz` (JWT) | Posible token JWT |
| `api_key=valor_largo` | Posible valor de API key |
| `Authorization: Bearer token` | Posible Bearer token |
| `token=valor_largo` | Posible valor de token |

## Recomendaciones de seguridad

1. **Añada `.env` a `.gitignore`** — ya está incluido por defecto.
2. **No escriba claves en código Python** — use siempre `os.getenv()` o `.env`.
3. **Revise `.claude/settings.local.json`** — puede contener API keys de sesiones
   anteriores. Este archivo está excluido de git (`/.claude/` en `.gitignore`).
4. **Rote claves comprometidas** — si `secrets-scan` detecta un secreto en git
   history, cámbielo inmediatamente en el servicio correspondiente.
5. **No comparta informes de config-check** — aunque los valores están enmascarados,
   los fragmentos visibles pueden facilitar ataques de fuerza bruta.

## Relación con .gitignore

El `.gitignore` del proyecto garantiza que no se versionen:

```gitignore
.env
.env.*
!.env.example    ← .env.example SÍ se versiona
```

Y también:
```gitignore
.claude/         ← incluye settings.local.json
expediente-EIA-*/
tmp/
```

## API Python

```python
from eia_agent.core.config_manager import validate_config, mask_secret

# Validar configuración actual
result = validate_config()
print(result.summary())
print(result.is_valid())  # True si no hay ERRORs

# Enmascarar un secreto antes de mostrarlo
safe = mask_secret("abcdefghijklmnopqrstuvwxyz")
print(safe)  # → "abcd...wxyz"

# Escanear secretos en un directorio
from eia_agent.core.config_manager import scan_repo_for_potential_secrets
result = scan_repo_for_potential_secrets(".")
print(result.status)  # OK | NO_CONFORME
```

## Cómo ejecutar los tests

```
venv\Scripts\python -m unittest tests.test_config_manager
```

Suite completa (99 tests):
- `TestMaskSecret` — 8 tests
- `TestIsPlaceholderValue` — 12 tests
- `TestLoadDotenvFile` — 7 tests
- `TestReadEnvVarStatus` — 8 tests
- `TestValidateConfig` — 10 tests
- `TestBuildConfigReportMarkdown` — 7 tests
- `TestWriteConfigValidationOutputs` — 6 tests
- `TestScanTextForPotentialSecrets` — 7 tests
- `TestScanFileForPotentialSecrets` — 4 tests
- `TestScanRepoForPotentialSecrets` — 7 tests
- `TestCLIConfigCheck` — 4 tests
- `TestCLISecretsScan` — 3 tests
- `TestDataclasses` — 8 tests
- `TestConstantes` — 8 tests

Todos usan `tempfile.TemporaryDirectory` — no modifican expedientes piloto.

## Códigos de incidencia

| Código | Severidad | Descripción |
|--------|-----------|-------------|
| `BE04-E001` | ERROR | Variable obligatoria ausente |
| `BE04-E002` | ERROR | Variable obligatoria con placeholder |
| `BE04-E003` | ERROR | Posible secreto detectado en archivo |
| `BE04-W001` | WARNING | Variable opcional ausente (allow_missing=False) |
| `BE04-W002` | WARNING | Variable opcional con placeholder |
| `BE04-W003` | WARNING | EIA_ENV con valor no reconocido |
| `BE04-I001` | INFO | Variable opcional ausente (comportamiento normal) |
