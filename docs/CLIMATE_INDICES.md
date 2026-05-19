# CLIMATE_INDICES — CL-03

Módulo Python puro para clasificación climática a partir de datos mensuales.

## Qué hace CL-03

- Calcula el **índice de aridez de Martonne** (I = P / (T + 10)).
- Clasifica el clima según **Köppen-Geiger** (implementación simplificada, hemisferio norte).
- Detecta **meses secos** según el criterio de **Walter-Gaussen** (P ≤ 2·T).
- Devuelve un resumen estructurado (`ClimateClassification`) con todos los índices.
- Parsea datos de normales AEMET OpenData a formato interno.

## Qué NO hace CL-03

- **No llama a AEMET** ni a ningún servicio HTTP (eso es CL-01).
- **No selecciona estaciones** climáticas (eso es CL-02).
- **No genera climogramas** ni ningún gráfico (eso es CL-04).
- **No redacta** el bloque climático definitivo del DA (eso es AG-10).
- **No calcula normales** — trabaja con datos ya normalizados o fixtures.
- **No escribe archivos** en disco.

## Relación con CL-01 y CL-02

```
CL-01 (AEMETClient)
  └─► descarga normales JSON de AEMET para una estación
        │
CL-02 (ClimateStationSelector)
  └─► selecciona la estación más cercana al proyecto
        │
CL-03 (ClimateIndices)  ◄── este módulo
  └─► calcula Köppen, Martonne, Gaussen a partir de los datos descargados
        │
CL-04 (climograma) — pendiente
  └─► genera PNG con curva de temperatura + barras de precipitación
```

---

## Importación

```python
from eia_agent.core.climate_indices import (
    MonthlyClimateData,
    ClimateClassification,
    martonne_index,
    classify_martonne,
    gaussen_dry_months,
    month_names_es,
    classify_koppen,
    classify_climate,
    parse_monthly_climate_from_aemet_normals,
)
```

---

## Clases de datos

### `MonthlyClimateData`

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `temperatures_c` | `list[float]` | Sí | 12 temperaturas medias mensuales (°C) |
| `precipitations_mm` | `list[float]` | Sí | 12 precipitaciones medias mensuales (mm) |
| `station_id` | `str \| None` | No | Identificador de estación |
| `station_name` | `str \| None` | No | Nombre de estación |
| `period` | `str \| None` | No | Periodo de referencia (p.ej. "1991-2020") |
| `source` | `str \| None` | No | Fuente de los datos |

**Métodos estadísticos:** `annual_temperature()`, `annual_precipitation()`, `coldest_month_temp()`, `warmest_month_temp()`, `driest_month_precipitation()`, `wettest_month_precipitation()`.

**Serialización:** `to_dict()` / `from_dict(data)`.

**Validación:** `validate()` — lanza `ValueError` si hay ≠12 meses o precipitación negativa.

---

### `ClimateClassification`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `koppen_code` | `str` | Código Köppen (BWh, Csa, Cfb...) |
| `koppen_label` | `str` | Etiqueta descriptiva en español |
| `martonne_index` | `float` | Índice de Martonne calculado |
| `martonne_label` | `str` | Categoría de aridez |
| `dry_months_gaussen` | `list[int]` | Meses secos 1-12 (enero=1) |
| `dry_months_names` | `list[str]` | Nombres en español de los meses secos |
| `annual_temperature_c` | `float` | Temperatura anual media (°C) |
| `annual_precipitation_mm` | `float` | Precipitación anual total (mm) |
| `notes` | `list[str]` | Notas sobre la clasificación |
| `warnings` | `list[str]` | Avisos (p.ej. Martonne no calculable) |

---

## Fórmula de Martonne

```
I = P / (T + 10)
```

Donde:
- P = precipitación media anual (mm)
- T = temperatura media anual (°C)

| Rango de I | Categoría |
|-----------|-----------|
| < 5 | árido extremo |
| 5 – 10 | árido |
| 10 – 20 | semiárido |
| 20 – 30 | subhúmedo |
| 30 – 60 | húmedo |
| ≥ 60 | muy húmedo |

Lanza `ValueError` si T ≤ -10 °C (denominador ≤ 0).

**Ejemplo Lanzarote:** P ≈ 131 mm, T ≈ 21.4 °C → I = 131 / 31.4 ≈ **4.2** → árido extremo.

---

## Criterio de Gaussen

Mes seco si: **P ≤ 2·T**

- P = precipitación mensual (mm)
- T = temperatura media mensual (°C)

Los meses se devuelven como índices 1-12 (enero = 1).

Nota: el criterio no se aplica a meses con T < 0 (2·T negativo → P ≥ 0 > 2·T, nunca seco).

---

## Lógica simplificada de Köppen

**Orden de evaluación** (hemisferio norte):

```
1. Polar E   → T_warm ≤ 10 °C  (ET si > 0°C, EF si ≤ 0°C)
2. Seco B    → P anual < Pth
3. Tropical A → T_cold ≥ 18 °C  (Af / Am / Aw)
4. Templado C → -3 < T_cold < 18 °C  y  T_warm > 10 °C
5. Continental D → T_cold ≤ -3 °C  y  T_warm > 10 °C
```

**Umbral Pth para clima seco B:**

| Condición de distribución de lluvia | Pth |
|------------------------------------|-----|
| ≥ 70 % en verano (abr-sep) | 20·T + 280 |
| ≥ 70 % en invierno (oct-mar) | 20·T |
| Resto (distribución uniforme) | 20·T + 140 |

- P < 0.5·Pth → **BW** (desierto)
- P < Pth → **BS** (estepa)
- Sufijo térmico: **h** si T_anual ≥ 18 °C, **k** si T_anual < 18 °C

**Sufijo de estación seca (grupos C y D):**
- **s** (verano seco): mes más seco verano < 40 mm  Y  ≤ 1/3 del mes más lluvioso invierno
- **w** (invierno seco): mes más seco invierno ≤ 1/10 del mes más lluvioso verano
- **f** (sin estación seca clara)

**Sufijo térmico (grupos C y D):**
- **a** si T_warm ≥ 22 °C
- **b** si T_warm < 22 °C y ≥ 4 meses > 10 °C
- **c** si < 4 meses > 10 °C

### ⚠️ Advertencia sobre precisión

La implementación es **técnica y simplificada**. Usar con cautela cuando el emplazamiento esté cerca de los umbrales de clasificación (especialmente B/C, Cs/Cf, A/B). Para expedientes donde la clasificación climática sea determinante, contrastar con atlas climáticos o fuentes especializadas.

Todos los resultados incluyen la nota: *"Clasificación Köppen-Geiger calculada mediante implementación simplificada; revisar en expediente definitivo si el resultado es sensible al umbral."*

---

## Ejemplos de uso

```python
from eia_agent.core.climate_indices import MonthlyClimateData, classify_climate

# Datos de Lanzarote (aproximados)
data = MonthlyClimateData(
    temperatures_c  =[17.8,18.1,18.8,19.4,20.7,22.7,24.9,25.7,25.1,23.5,21.0,18.6],
    precipitations_mm=[22.0,19.0,15.0, 7.0, 2.0, 1.0, 0.0, 1.0, 5.0,14.0,21.0,24.0],
    station_id="C029O",
    station_name="Lanzarote Aeropuerto",
    period="1991-2020",
)

result = classify_climate(data)
print(result.summary())
# Köppen: BWh — Árido desértico cálido (BWh)
# Martonne: 4.2 (árido extremo)
# T anual: 21.4 °C  |  P anual: 131.0 mm
# Meses secos (Gaussen): Enero, Febrero, ...
```

```python
# Desde normales AEMET
from eia_agent.core.climate_indices import parse_monthly_climate_from_aemet_normals

# aemet_data es la lista de dicts devuelta por AEMETClient.get_normales_climatologicas()
data = parse_monthly_climate_from_aemet_normals(aemet_data, station_id="C029O")
result = classify_climate(data)
print(result.to_dict())
```

---

## Cómo ejecutar los tests

```bash
# Suite CL-03 únicamente
venv\Scripts\python -m pytest tests/test_climate_indices.py -v

# Suite completa del proyecto
venv\Scripts\python -m unittest discover -s tests
```

77 tests OK. Sin dependencias externas. Sin llamadas a AEMET.

---

## Dependencias

Solo stdlib de Python ≥ 3.11:
- `dataclasses`, `math` (implícito en float NaN)

Sin dependencias de terceros.

---

## Limitaciones conocidas

- Solo hemisferio norte (verano = abril-septiembre).
- Grupos D sin distinción del sufijo `d` (T_cold < -38 °C, casos extremos).
- El parser AEMET solo extrae `tm_mes` y `pr_mes` — no otros campos de normales.
- No valida la calidad estadística de los datos de entrada.
- No tiene en cuenta la altitud para correcciones de temperatura.
