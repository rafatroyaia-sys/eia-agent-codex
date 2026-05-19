# ENVIRONMENT_VARIABLES — Variables de entorno de EIA-Agent

Este documento describe todas las variables de entorno que el sistema puede necesitar,
para qué sirven, en qué fase se usan y cómo configurarlas.

**Regla absoluta**: ninguna clave real aparece en este documento ni en ningún
archivo versionado en git. Las claves se gestionan exclusivamente via `.env` local
(no versionado) o variables de entorno del sistema operativo.

---

## Configuración rápida

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Edita `.env` y añade tus claves reales. El archivo `.env` está en `.gitignore` y
nunca debe subirse al repositorio.

---

## Variables documentadas

### `AEMET_API_KEY`

| Campo | Valor |
|-------|-------|
| **Para qué sirve** | Autenticar peticiones a la API AEMET OpenData para descarga de normales climatológicas 1981-2010, datos de temperatura y precipitación por estación. |
| **¿Obligatoria ahora?** | No para instalar ni para fases 1-3. **Sí** a partir de Fase 4 (AG-7, clima) cuando se ejecute `AEMETClient.get_normales_climatologicas()`. |
| **Fase que la usa** | Fase 4 — Geodatos (AG-7: clima, estación de referencia, climograma) |
| **Módulo Python** | `src/eia_agent/core/aemet_client.py` — `AEMETClient.from_env()` |
| **Dónde obtenerla** | https://opendata.aemet.es/centrodedescargas/altaUsuario (registro gratuito) |
| **Si falta** | `AEMETConfigError: AEMET_API_KEY no configurada` |

---

### `MAPBOX_TOKEN`

| Campo | Valor |
|-------|-------|
| **Para qué sirve** | Acceder a mapas base de alta resolución de Mapbox como fuente alternativa o complementaria a los WMS institucionales (IDECanarias, GRAFCAN, IGN). |
| **¿Obligatoria ahora?** | No. El sistema funciona con WMS institucionales gratuitos. Esta clave es un fallback adicional para cartografía base. |
| **Fase que la usa** | Fase 4 — Geodatos (AG-6: cartografía, CA-02 cliente WMS, cuando esté implementado) |
| **Módulo Python** | Pendiente — CA-02 (cliente WMS, no implementado aún) |
| **Dónde obtenerla** | https://account.mapbox.com/ (plan gratuito con límite de peticiones) |
| **Si falta** | El sistema usa únicamente WMS institucionales. Sin error fatal. |

---

### `OPENAI_API_KEY`

| Campo | Valor |
|-------|-------|
| **Para qué sirve** | Configurar un agente con modelo GPT como alternativa o fallback al modelo Claude (Anthropic). El sistema usa Claude por defecto. |
| **¿Obligatoria ahora?** | No. EIA-Agent usa Claude (Anthropic) como modelo principal. Esta clave solo sería necesaria si se configura un agente GPT explícitamente. |
| **Fase que la usa** | Pendiente — ninguna fase actual la requiere. Reservada para P2/P3 si se implementa soporte multi-modelo. |
| **Módulo Python** | No implementado. |
| **Dónde obtenerla** | https://platform.openai.com/api-keys |
| **Si falta** | Sin efecto — el sistema usa Claude. |

---

### `EIA_ENV`

| Campo | Valor |
|-------|-------|
| **Para qué sirve** | Controla el entorno de ejecución: activa mocks de APIs externas en CI, habilita restricciones adicionales en producción. |
| **¿Obligatoria ahora?** | No. Valor por defecto: `local`. |
| **Valores válidos** | `local` (máquina del técnico), `ci` (integración continua, mocks activos), `prod` (servidor, todas las claves requeridas) |
| **Fase que la usa** | Todas las fases — condiciona el comportamiento de tests y el cliente AEMET. |

---

## Ejemplo de `.env`

```dotenv
# Copiar como .env y rellenar con claves reales
# NUNCA subir este archivo a git

AEMET_API_KEY=
MAPBOX_TOKEN=
OPENAI_API_KEY=
EIA_ENV=local
```

---

## Verificar configuración

```bash
# Comprobar que AEMET_API_KEY está disponible antes de Fase 4
python run_expediente.py PARCELA phase4-precheck

# O directamente desde Python
python -c "import os; print('AEMET OK' if os.getenv('AEMET_API_KEY') else 'AEMET NO CONFIGURADA')"
```

---

## Seguridad

- `.env` está en `.gitignore` — nunca se versiona.
- `.env.example` está en git — solo con valores vacíos.
- El módulo `AEMETClient` nunca imprime la clave en logs.
- Los tests unitarios usan claves ficticias (`"test-key"`) — sin llamadas reales.
