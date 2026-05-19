# Especificación técnica AG-07 — Agente climático definitivo
## EIA-Agent v2.1 — Productización P2

**Versión**: 1.0  
**Fecha**: 2026-04-15  
**Estado**: VALIDADO — baseline piloto-recimetal + mejoras P2  
**Aplicabilidad**: todos los expedientes EIA en Canarias

---

## 1. Resumen ejecutivo

AG-07 es el agente climático del sistema. Su misión es producir la caracterización climática del emplazamiento con datos oficiales AEMET, clasificar el clima, identificar los riesgos naturales con relevancia para la EIA, y generar el climograma Walter-Lieth. Todos los productos quedan trazados a fuentes verificables con estado de evidencia explícito.

El piloto RECIMETAL validó el flujo principal (AEMET OpenData → JSON → CSV → SVG → MD). Esta especificación formaliza ese flujo, corrige sus debilidades y define el estándar de producción frente al modo test.

---

## 2. Criterios de selección de estación meteorológica

### 2.1 Criterio primario: representatividad climática

La estación debe cumplir **los cuatro criterios** siguientes:

| Criterio | Valor aceptable | Valor límite | Acción si se supera |
|----------|----------------|--------------|---------------------|
| Distancia al proyecto | ≤ 15 km | 15–25 km | Justificar homogeneidad climática; registrar como INFERIDO |
| Diferencia de altitud | ≤ 200 m | 200–500 m | Aplicar corrección adiabática (−0,65°C / 100 m); registrar |
| Exposición / vertiente | Misma vertiente (N vs S en Canarias) | Diferente vertiente | GAP de criticidad MEDIA |
| Distancia > 25 km | — | > 25 km | GAP de criticidad ALTA. AG-07 no puede continuar sin justificación explícita del promotor |

> **Canarias**: las islas tienen microclimas por vertientes muy marcados. Una estación a 20 km pero en la vertiente húmeda del norte no es representativa de un proyecto en la vertiente seca del sur. La distancia es condición necesaria pero no suficiente.

### 2.2 Orden de selección

1. Estación con serie de normales climatológicas completa en el mismo municipio.
2. Estación con datos completos en el mismo clima topográfico (costa, medianías, cumbre) aunque en municipio distinto.
3. Estación sinóptica más cercana con serie larga (≥ 20 años).
4. Si no hay ninguna válida: declarar GAP-CLIMA de criticidad ALTA y detener AG-07.

### 2.3 Estaciones de referencia por isla (Canarias)

| Isla | Estación principal | Indicativo | Zona | Altitud |
|------|-------------------|-----------|------|---------|
| Lanzarote | Lanzarote Aeropuerto | C029O | Costera E | 14 m |
| Fuerteventura | Fuerteventura Aeropuerto | C659A | Costera E | 25 m |
| Gran Canaria | Las Palmas / Gando | C029P | Costera E | 24 m |
| Tenerife (sur) | Tenerife Sur / Reina Sofía | C449C | Costera S | 64 m |
| Tenerife (norte) | Tenerife Norte / Los Rodeos | C449A | Medianías N | 617 m |
| La Palma | La Palma Aeropuerto | C447A | Costera O | 32 m |
| La Gomera | Playa Santiago | C449I | Costera S | 50 m |
| El Hierro | El Hierro Aeropuerto | C929I | Costera S | 32 m |

> Estas estaciones son las principales. AG-07 debe verificar en cada expediente que la estación seleccionada tiene datos disponibles para el periodo solicitado en AEMET OpenData antes de registrarla como fuente.

### 2.4 Documentación de la selección

AG-07 debe registrar en `datos_climaticos.json`, campo `justificacion_seleccion`:
- Estación seleccionada y por qué.
- Distancia y dirección al proyecto.
- Diferencia de altitud.
- Si hay estaciones más cercanas descartadas, por qué se descartaron.

---

## 3. Serie de datos preferente

### 3.1 Jerarquía de periodos

| Prioridad | Periodo | Estado | Cuándo usar |
|-----------|---------|--------|-------------|
| 1 | Normales 1991-2020 | Preferente | Cuando disponibles en AEMET OpenData para la estación |
| 2 | Normales 1981-2010 | Aceptable | Si 1991-2020 no disponibles o la estación tiene serie incompleta |
| 3 | Serie observaciones ≥ 20 años | Aceptable con cautela | Solo si no hay normales; calcular estadísticos manualmente |
| 4 | Serie < 20 años | No aceptable en producción | GAP MEDIA; en test: WARNING |

> **Nota**: AEMET publicó las normales 1991-2020 en 2023. Para expedientes reales, verificar disponibilidad para la estación específica. El piloto RECIMETAL usó 1981-2010 por ser el único periodo disponible en el endpoint consultado en el momento del piloto.

### 3.2 Endpoints AEMET OpenData

| Recurso | Endpoint | Periodo | Uso |
|---------|---------|---------|-----|
| Normales climatológicas | `/opendata/api/valores/climatologicos/normales/estacion/{indicativo}` | 1981-2010 | Flujo principal piloto |
| Normales 1991-2020 | `/opendata/api/valores/climatologicos/normalesClimatologicas/estacion/{indicativo}` | 1991-2020 | Preferente — verificar disponibilidad |
| Extremos climatológicos | `/opendata/api/valores/climatologicos/extremosClimatologicos/estacion/{indicativo}` | Histórico | Para P_max_24h, T_max_abs, T_min_abs |
| Inventario estaciones | `/opendata/api/valores/climatologicos/inventarioestaciones/todasestaciones` | — | Para buscar estaciones alternativas |

> **Autenticación**: API key personal requerida. Registrar en expediente que se usó API key pero no incluir el valor en los archivos del expediente.

---

## 4. Variables mínimas obligatorias

### 4.1 Bloque principal (normales mensuales)

| Variable | Campo AEMET | Unidad | Estado si falta |
|----------|------------|--------|-----------------|
| Temperatura media mensual | `tm_mes_md` | °C | PENDIENTE — bloquea |
| Temperatura máxima media | `ta_max_md` | °C | PENDIENTE — bloquea |
| Temperatura mínima media | `ta_min_md` | °C | PENDIENTE — bloquea |
| Precipitación media mensual | `p_mes_md` | mm | PENDIENTE — bloquea |
| Humedad relativa media | `hr_md` | % | ESTIMADO si falta; WARNING |
| Velocidad media del viento | `w_med_md` | km/h | PENDIENTE — bloquea (relevante para EIA) |
| Insolación media diaria | `inso_md` | h/día | ESTIMADO si falta; WARNING |

### 4.2 Bloque de viento (obligatorio en Canarias)

| Variable | Campo AEMET | Unidad | Obligatorio en Canarias |
|----------|------------|--------|------------------------|
| Velocidad media anual | calculado de `w_med_md` | km/h y m/s | Sí |
| Racha media mensual | `w_racha_md` | km/h | Sí |
| Días con racha >55 km/h | `nw_55_md` | días/mes | Sí — umbral relevante para dispersión |
| Días con racha >91 km/h | `nw_91_md` | días/mes | Sí — umbral de daño estructural |
| Dirección dominante | No disponible en endpoint normales | — | Documentar ausencia; fuente alternativa |

> **Rosa de vientos**: no disponible en el endpoint de normales climatológicas. Para expedientes que requieran análisis de dirección (dispersión de contaminantes, emisiones difusas), indicar como PENDIENTE y referenciar al Atlas de Climatología de Canarias (AEMET) o a datos de la red de estaciones sinópticas.

### 4.3 Bloque de extremos (consulta separada)

| Variable | Uso EIA |
|----------|---------|
| Precipitación máxima en 24h | Dimensionamiento de drenaje, riesgo de inundación puntual |
| Temperatura máxima absoluta | Riesgo de incendio, confort laboral, materiales |
| Temperatura mínima absoluta | Riesgo de helada (generalmente inexistente en costas canarias) |

Obtener del endpoint de extremos. Si no disponible: registrar como PENDIENTE con estado ESTIMADO a partir de T_max_abs y T_min_abs declaradas en normales; documentar en `notas`.

### 4.4 Variables no exigidas (registrar ausencia)

Las siguientes variables **no bloquean** el gate pero deben constar como no disponibles si no se obtienen:
- Rosa de vientos (dirección dominante).
- ETP Penman-Monteith.
- Días de calima / polvo en suspensión (fuente alternativa: AEMET alertas o IDECanarias).
- Número de días de lluvia, tormenta, granizo.

---

## 5. Formato de tabla climática

### 5.1 Estructura obligatoria

La tabla mensual en `descripcion_clima.md` debe tener este formato mínimo:

```
| Mes | T_med (°C) | T_max (°C) | T_min (°C) | P (mm) | HR (%) | Vto (km/h) | Insol. (h/d) | Días_v>55 |
```

Con fila ANUAL al final que incluya:
- T_media anual, T_max absoluta (indicar "(abs)"), T_min absoluta (indicar "(abs)")
- P_total anual
- HR_media anual
- Viento medio anual en km/h y m/s
- Insolación media anual en h/día
- Total días/año con rachas >55 km/h

### 5.2 Notas de pie obligatorias bajo la tabla

```
*Fuente: AEMET OpenData — Normales climatológicas [periodo], estación [indicativo] — [nombre]*  
*Distancia al proyecto: [X] km [dirección]. Diferencia de altitud: [Y] m.*  
*T_max y T_min anuales son valores absolutos del período; mensuales son medias de máximas/mínimas.*
```

### 5.3 CSV de acompañamiento

El archivo `tabla_climatologica.csv` debe incluir:
- Cabecera con metadatos de la estación (indicativo, nombre, coordenadas, altitud, periodo).
- Fila de unidades explícitas antes de los datos.
- Separador: punto y coma (`;`) para compatibilidad con LibreOffice en locale español.
- Última fila: clasificación Köppen, índice de Martonne, estación seca.

---

## 6. Formato del climograma

### 6.1 Tipo: Walter-Lieth

El climograma estándar de AG-07 sigue la convención Walter-Lieth (Gaussen):

- **Escala temperatura**: eje Y izquierdo, °C.
- **Escala precipitación**: eje Y derecho, mm. Relación: 1°C = 2 mm (zona árida/semiárida).
- **Período seco**: meses donde la curva de precipitación está por debajo de la curva de temperatura en escala Walter-Lieth (P < 2T). Sombreado en amarillo o naranja.
- **Período húmedo**: sombreado en azul claro.

### 6.2 Elementos obligatorios del SVG

| Elemento | Obligatorio |
|----------|-------------|
| Título: "CLIMOGRAMA — [topónimo / isla]" | Sí |
| Subtítulo: estación, período, fuente | Sí |
| Curva de temperatura (línea roja) | Sí |
| Barras de precipitación (azul) | Sí |
| Sombreado período seco | Sí |
| Etiquetas de meses en eje X | Sí |
| Doble eje Y con unidades | Sí |
| Leyenda (T°C / P mm) | Sí |
| Nota de clasificación Köppen e índice Martonne | Recomendado |

### 6.3 Dimensiones y formato de salida

| Modo | Formato | Dimensiones | DPI equivalente | Uso |
|------|---------|-------------|----------------|-----|
| Test | SVG (vector) | 900 × 560 px | N/A (vector) | Verificación visual |
| Producción (DA final) | SVG exportado a PNG | ≥ 2480 × 1748 px | 300 DPI A4 apaisado | Inserción en DOCX/PDF |

> **El SVG es el master**. La conversión a PNG 300 DPI la realiza M-11 en el ensamblaje. AG-07 genera siempre el SVG; nunca genera PNG directamente.

### 6.4 Limitación conocida del piloto

La escala Walter-Lieth estándar (P = 2T) funciona bien cuando P < 100 mm/mes. Para Lanzarote (P_max_mes = 21,4 mm) la escala es adecuada. Para islas con precipitaciones más altas (La Palma, parte de Tenerife norte) la escala puede necesitar ajuste: si el mes más lluvioso supera 100 mm, aplicar escala P = 4T o P = 10T según convención, e indicarlo en el climograma.

---

## 7. Tratamiento de valores faltantes

| Situación | Tratamiento | Estado de evidencia |
|-----------|-------------|---------------------|
| Variable ausente en respuesta API (campo null) | Registrar como `-` en tabla; documentar en `trazabilidad.variables_no_disponibles` | PENDIENTE |
| Mes concreto con dato faltante | No interpolar. Marcar mes como `N/D`. Si > 3 meses: GAP MEDIA | PENDIENTE |
| Variable entera no disponible pero no bloqueante | Registrar ausencia; estimar si hay fuente alternativa documentada | ESTIMADO |
| Variable bloqueante no disponible | GAP de criticidad ALTA. Detener AG-07 | PENDIENTE |
| Dato disponible pero de calidad dudosa (serie < 15 años) | Aceptar con estado INFERIDO + nota de cautela sobre representatividad | INFERIDO |

> **Regla de prudencia**: nunca rellenar huecos por interpolación sin documentarlo explícitamente. El expediente debe reflejar exactamente lo que tiene AEMET, no una versión mejorada artificialmente.

---

## 8. Clasificación climática

AG-07 calcula y documenta obligatoriamente:

### 8.1 Köppen-Geiger (obligatorio)

Seguir el árbol de decisión completo con el factor estacional de Walter:
1. Determinar si P_anual < P_umbral (árido B) o ≥ P_umbral (húmedo).
2. Para B: calcular P_umbral con el régimen estacional (si >70% lluvia en verano: P_r = 20T; si >70% en invierno: P_r = 20T + 280; si no: P_r = 20T + 140).
3. Subcategorías W (desierto: P < P_r/2) vs S (estepa: P < P_r).
4. Subcategorías térmicas: h (T_anual > 18°C), k (T_anual < 18°C).
5. Documentar el cálculo completo, no solo la letra final.

### 8.2 Índice de aridez de Martonne (obligatorio en Canarias)

`I = P_anual / (T_media_anual + 10)`

Escala de referencia:
- I < 5: Hiperárido
- 5 ≤ I < 10: Árido
- 10 ≤ I < 20: Semiárido
- 20 ≤ I < 30: Subhúmedo seco
- 30 ≤ I < 60: Subhúmedo húmedo
- I ≥ 60: Húmedo

### 8.3 Estación seca (criterio de Gaussen)

Un mes es seco si P (mm) < 2 × T_media (°C).
Documentar: número de meses secos, cuáles son, y si la estación seca es continua o discontinua.

### 8.4 Clasificaciones opcionales

- Lang (solo si se pide análisis detallado de aridez).
- Thornthwaite (solo si se dispone de ETP).

---

## 9. Bloque de riesgos naturales

### 9.1 Estructura del bloque

Cada riesgo se documenta con el esquema:
```json
{
  "tipo": "nombre del riesgo",
  "nivel": "ALTO | MEDIO | BAJO | RESIDUAL",
  "descripcion": "qué es, magnitud cuantitativa si disponible",
  "fuente": "AEMET / IDECanarias RIESGOMAP / IGME / PGRI / ...",
  "relevancia_eia": "qué impacto tiene sobre la valoración ambiental del proyecto",
  "medidas_asociadas": "medidas o condicionantes que se derivarán en Fase 6"
}
```

### 9.2 Riesgos a evaluar obligatoriamente en Canarias

| Riesgo | Fuente de datos | Umbral de nivel ALTO |
|--------|---------------|----------------------|
| Viento intenso | AEMET normales (`nw_55_md`) | > 80 días/año con rachas >55 km/h |
| Calima / polvo sahariano | AEMET + nota cualitativa | Frecuencia estacional documentada |
| Sequía prolongada | AEMET (meses secos Gaussen) | ≥ 4 meses secos consecutivos |
| Inundación pluvial / costera | IDECanarias RIESGOMAP (MAP-006) | Presencia en zona T500 o costera |
| Actividad volcánica / sísmica | IGME + INVOLCAN + distancia a erupción histórica | < 5 km de zona volcánica activa |

### 9.3 Fuentes adicionales para riesgos

- **Inundación**: PGRI de la demarcación hidrográfica correspondiente (Decreto 111/2024 para Lanzarote).
- **Volcánico/sísmico**: Instituto Volcanológico de Canarias (INVOLCAN), series sísmicas IGN.
- **Calima**: Agencia Estatal de Meteorología, Atlas Climático de Canarias.

### 9.4 Referencia a cambio climático (obligatoria)

Todos los expedientes en Canarias deben incluir una nota de cambio climático en virtud de la **Ley 6/2022, de 13 de octubre, de Cambio Climático de Canarias** (modificada por Decreto-ley 5/2024 y Decreto-ley 1/2026). La nota debe mencionar:
- Tendencia de temperatura observada en Canarias (+0,3°C/década según AEMET).
- Tendencia de precipitación (reducción en décadas recientes, especialmente verano).
- Implicación para el proyecto: los datos históricos son orientativos; el horizonte temporal del proyecto puede diferir del clima histórico.

---

## 10. Diferencias entre modo test y salida final (producción)

| Aspecto | Modo `--test` | Modo producción |
|---------|--------------|-----------------|
| Periodo de datos | 1981-2010 si es lo disponible | Verificar si existen normales 1991-2020 |
| Extremos | No requeridos | Sí — consultar endpoint extremos |
| Rosa de vientos | Ausencia documentada como PENDIENTE | Fuente alternativa identificada o GAP |
| DPI climograma | SVG (no se convierte) | SVG + exportación 300 DPI en M-11 |
| Variables faltantes | WARNING, no bloquea | ERROR si son bloqueantes |
| Nota cambio climático | Párrafo genérico | Verificar normativa vigente en el momento |
| Validación final | Gate: WARNING si hay PENDIENTE | Gate: ERROR si hay PENDIENTE bloqueante |

---

## 11. Lecciones del piloto RECIMETAL para AG-07

### 11.1 Qué funcionó bien

1. **Flujo AEMET API**: HTTP 200 con datos completos los 12 meses + anual. El endpoint de normales climatológicas es estable y fiable para las estaciones principales de Canarias.
2. **Selección de estación C029O**: 6,5 km, misma zona costera, diferencia altitudinal de 14 m. Criterio correcto y bien justificado. Patrón a reutilizar en Lanzarote.
3. **Análisis de viento**: fue la sección más valiosa para la EIA. La cuantificación de 99,2 días/año con rachas >55 km/h es el dato más relevante del bloque climático para una instalación de gestión de residuos metálicos.
4. **Clasificación BWh + Martonne 3,23**: correcta, bien documentada con cálculo paso a paso. Este nivel de detalle es el estándar.
5. **Bloque de riesgos naturales**: 5 riesgos identificados con nivel y relevancia para EIA. Estructura directamente usable en AG-09.
6. **SVG Walter-Lieth**: generado correctamente en modo test. La doble escala es coherente con P_max = 21,4 mm. El SVG como master es la decisión correcta.
7. **Nota de cambio climático**: referencia correcta a Ley 6/2022 y tendencia AEMET. Debe mantenerse como sección obligatoria.
8. **Trazabilidad completa**: endpoint, fecha, variables obtenidas, variables no disponibles. Nivel de documentación correcto.

### 11.2 Limitaciones y debilidades

1. **Periodo 1981-2010, no 1991-2020**: en el piloto no se verificó si existían normales 1991-2020 para C029O. Para expedientes reales, verificar primero el endpoint del periodo más reciente.
2. **Sin datos de extremos**: P_max_24h, T_max_abs y T_min_abs no se obtuvieron del endpoint de extremos. Se usaron los valores de T_max_abs y T_min_abs del endpoint de normales (37,4°C / 10,6°C), que son datos del período, no del endpoint de extremos. Esto es aceptable en test pero incompleto para producción.
3. **Sin rosa de vientos**: documentado como no disponible, pero sin indicar fuente alternativa. El agente definitivo debe referenciar el Atlas Climático de Canarias (AEMET) como alternativa.
4. **horas_sol_mes inconsistente**: los valores mensuales (63–74 h/mes) sumaban 808 h/año, lo que es claramente incorrecto (Lanzarote tiene ~2.800 h/año de sol). El campo `p_sol_md` de AEMET parece medir otra cosa (posiblemente porcentaje de insolación posible, no horas absolutas). La descripción_clima.md lo detectó y anotó la discrepancia pero no la resolvió. En el agente definitivo: no usar `p_sol_md` como horas absolutas de sol sin verificar su definición en el endpoint.
5. **Sin estación alternativa documentada**: si C029O no responde, no hay fallback definido. El agente definitivo debe documentar al menos una estación alternativa por isla.
6. **Calima sin fuente cuantitativa**: el riesgo de calima se describió cualitativamente sin citar días/año de episodios. Documentar como DECLARADO/cualitativo con fuente citada.

### 11.3 Criterios de mejora para el agente definitivo

- Añadir verificación del periodo 1991-2020 como primer paso.
- Añadir llamada al endpoint de extremos como paso 2.
- Documentar `p_sol_md` como "porcentaje de insolación relativa o magnitud a verificar" — no usar como horas absolutas sin confirmación.
- Incluir estaciones alternativas en la documentación de selección.
- Añadir fuente del Atlas Climático de Canarias para rosa de vientos.

---

## 12. Criterios de gate para Fase 4B

El gate de Fase 4B (clima) pasa si:

| Criterio | Test | Producción |
|----------|------|-----------|
| `datos_climaticos.json` existe y tiene los 12 meses completos | OK | OK |
| `tabla_climatologica.csv` generada | OK | OK |
| `climograma.svg` generado | OK | OK |
| `descripcion_clima.md` generada | OK | OK |
| Clasificación Köppen calculada y documentada | OK | OK |
| Índice de Martonne calculado | OK | OK |
| Bloque de riesgos naturales con ≥ 3 riesgos | OK | OK |
| Nota de cambio climático presente | OK | OK |
| Variables bloqueantes todas en estado ≠ PENDIENTE | WARNING | ERROR |
| Datos de extremos obtenidos | WARNING si falta | ERROR si falta |
| Estación con distancia > 25 km | ERROR (siempre) | ERROR |

---

*Especificación generada por EIA-Agent v2.1 — Productización P2 — 2026-04-15*
