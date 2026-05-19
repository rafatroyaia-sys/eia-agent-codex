# AEMET_CLIENT — CL-01

Cliente HTTP reutilizable para la API OpenData de AEMET.

**No selecciona estación climática. No calcula Köppen. No genera climogramas. No escribe archivos.**

## Módulo

`src/eia_agent/core/aemet_client.py`

## Relación con módulos del bloque climático

```
AEMETClient (CL-01)   ← este módulo
        │
CL-02 selector_estacion_mas_proxima()
        │
   ┌────┴────┐
CL-03      CL-04
Köppen    PNG climograma
           │
         CL-05
       Inserción DOCX
```

## Qué hace CL-01

1. **Autenticación por API key** — lee `AEMET_API_KEY` del entorno o acepta la clave explícitamente.
2. **Patrón dos pasos de AEMET** — la API OpenData devuelve primero una URL temporal (`"datos"`),
   que hay que descargar para obtener el JSON final. El cliente gestiona ambos pasos de forma
   transparente.
3. **Retry con backoff exponencial** — reintenta en HTTP 429 (rate limit) y 5xx (errores del servidor).
   Backoff: 1s → 2s → 4s.
4. **Gestión tipada de errores** — jerarquía de excepciones específicas que permite distinguir
   fallos de autenticación, no encontrado, timeout, rate limit, etc.

## Qué NO hace CL-01

- No selecciona la estación más próxima a unas coordenadas (CL-02).
- No calcula clasificación Köppen-Geiger ni índice de Martonne (CL-03).
- No genera climogramas PNG (CL-04).
- No inserta imágenes en DOCX (CL-05).
- No escribe ningún archivo en disco.
- No usa IA ni llama a ningún servicio externo salvo AEMET.
- No valida que la API key sea correcta antes de la primera petición real.

## Configuración de AEMET_API_KEY

La clave se obtiene gratuitamente en [opendata.aemet.es](https://opendata.aemet.es).

Configurarla en `.env` del proyecto (INST-01 genera `.env.example`):

```
AEMET_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

El cliente lee la clave con `AEMETClient.from_env()`. Nunca se pasa hardcoded al código.

## API pública

### Excepciones

```
AEMETError (base)
├── AEMETConfigError    — API key ausente o vacía
├── AEMETAuthError      — HTTP 401 o 403
├── AEMETNotFoundError  — HTTP 404
├── AEMETTimeoutError   — timeout de requests
├── AEMETRateLimitError — HTTP 429 agotado tras retries
├── AEMETServiceError   — HTTP 5xx agotado tras retries
└── AEMETResponseError  — JSON inválido o estructura inesperada
```

Todas son instancias de `AEMETError` y pueden capturarse con un solo `except AEMETError`.

### AEMETClient

```python
class AEMETClient:
    def __init__(
        self,
        api_key: str,
        timeout: int = 10,
        max_retries: int = 3,
        base_url: str | None = None,
    ) -> None: ...

    @classmethod
    def from_env(cls) -> AEMETClient: ...

    def get_normales_climatologicas(self, id_estacion: str) -> object: ...
```

#### `from_env()`

```python
from eia_agent.core.aemet_client import AEMETClient, AEMETConfigError

try:
    client = AEMETClient.from_env()
except AEMETConfigError as e:
    print(f"Configura AEMET_API_KEY en .env: {e}")
```

Lee `AEMET_API_KEY` de `os.environ`. Lanza `AEMETConfigError` si no está o está vacía.

#### `get_normales_climatologicas(id_estacion)`

```python
client = AEMETClient.from_env()

try:
    normales = client.get_normales_climatologicas("C447A")
    # normales es una lista de dicts con los datos mensuales 1981-2010
    for mes in normales:
        print(mes["mes"], mes.get("p_mes"), mes.get("tm_mes"))
except AEMETNotFoundError:
    print("Estación no encontrada")
except AEMETRateLimitError:
    print("Rate limit — espere y reintente")
except AEMETError as e:
    print(f"Error AEMET: {e}")
```

- `id_estacion`: indicativo climatológico AEMET (ej. `"C447A"` = Las Palmas GC).
- Lanza `ValueError` si está vacío.
- Devuelve lista o dict con normales 1981-2010 en formato AEMET OpenData.

## Retry y errores

| Status HTTP | Comportamiento | Excepción final |
|-------------|---------------|-----------------|
| 200 | Éxito | — |
| 401, 403 | Error definitivo (no reintenta) | `AEMETAuthError` |
| 404 | Error definitivo (no reintenta) | `AEMETNotFoundError` |
| 429 | Reintenta hasta `max_retries` | `AEMETRateLimitError` |
| 5xx | Reintenta hasta `max_retries` | `AEMETServiceError` |
| Otros (400, 302…) | Error inmediato | `AEMETResponseError` |
| Timeout | Error inmediato (no reintenta) | `AEMETTimeoutError` |
| JSON inválido | Error inmediato | `AEMETResponseError` |
| Sin campo "datos" | Error inmediato | `AEMETResponseError` |

Backoff exponencial entre reintentos: `time.sleep(2 ** attempt)` → 1s, 2s, 4s.

## Cómo mockear en tests

Todas las llamadas HTTP usan `requests.get`. Para tests, parchear:

```python
from unittest.mock import patch, MagicMock

def _mock_response(status_code, json_data=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    return mock

# Mock del flujo completo (dos pasos)
metadata = {"estado": 200, "datos": "http://datos.test/abc"}
normales  = [{"mes": "1", "tm_mes": "18.5"}, {"mes": "2", "tm_mes": "19.0"}]

with patch("eia_agent.core.aemet_client.requests.get",
           side_effect=[_mock_response(200, metadata), _mock_response(200, normales)]):
    with patch.object(client, "_sleep_before_retry"):  # evitar esperas
        result = client.get_normales_climatologicas("C447A")
```

Para tests con retry, pasar una lista de respuestas como `side_effect`:
```python
# 2 errores 503 + 1 éxito
side_effect=[
    _mock_response(503),
    _mock_response(503),
    _mock_response(200, {"datos": "http://datos.test/x"}),
    _mock_response(200, normales),  # descarga datos URL
]
```

Para la clave de entorno:
```python
with patch.dict(os.environ, {"AEMET_API_KEY": "test_key"}, clear=False):
    client = AEMETClient.from_env()
```

## Base URL alternativa (para tests de integración local)

```python
# Apuntar a un servidor local mock
client = AEMETClient("test_key", base_url="http://localhost:8080/aemet-mock")
normales = client.get_normales_climatologicas("C447A")
# → GET http://localhost:8080/aemet-mock/api/valores/climatologicos/normales/estacion/C447A
```

## Limitaciones conocidas

1. **No valida la API key antes de usarla**: `AEMETClient("key")` no comprueba que
   la key sea válida. La detección ocurre en la primera petición real (HTTP 401).
2. **No reintenta en timeout ni errores de red**: un timeout único lanza `AEMETTimeoutError`
   inmediatamente. Si el servicio AEMET está caído, no reintentar más de `max_retries` veces.
3. **Solo cubre normales climatológicas**: `get_normales_climatologicas()` es el único
   método de datos implementado. Otros endpoints AEMET (observación, predicción, avisos)
   no están disponibles en esta versión.
4. **No implementa caché local**: cada llamada hace una petición real. Si se necesita
   reutilizar normales de la misma estación, el caller debe cachear el resultado.
5. **La URL de datos no requiere autenticación**: AEMET genera URLs temporales de descarga
   accesibles sin API key. Si la URL expira, devolverá error HTTP.

## Tests

`tests/test_aemet_client.py` — 84 tests, 9 clases, 1 skipped (integración).

Cobertura:
- `TestAEMETExceptions`: jerarquía, mensajes, catchability
- `TestAEMETClientInit`: constructor válido/inválido, valores por defecto, opciones
- `TestAEMETClientFromEnv`: con/sin AEMET_API_KEY, vacía, espacios
- `TestSleepBeforeRetry`: backoff 1s/2s/4s con `time.sleep` mockeado
- `TestRequestJson`: 200, 401, 403, 404, timeout, red, JSON inválido, status inesperado
- `TestRetryBehavior`: 2×503+éxito, 2×429+éxito, sleep count, retry exhausto
- `TestDownloadJsonFromDatosUrl`: lista, dict, error HTTP, JSON inválido, timeout, red
- `TestGetNormalesClimatologicas`: vacío/None, URL, headers, flujo datos, error propagación
- `TestFullTwoStepFlow`: flujo completo mockeando `requests.get`
- `TestAEMETIntegration`: llamada real (skipUnless `AEMET_API_KEY`)
