# Especificación cartográfica AG-06 — EIA-Agent v2.1

**Versión**: 1.0  
**Fecha**: 2026-04-15  
**Estado**: VALIDADO — baseline piloto-recimetal  
**Aplicabilidad**: todos los expedientes EIA en Canarias generados por el sistema

---

## 1. Resumen ejecutivo

AG-06 es el cartógrafo automático del sistema. Genera 8 mapas obligatorios a partir de servicios WMS/WFS públicos, sin herramientas GIS de escritorio, usando únicamente peticiones HTTP estándar a servicios INSPIRE y autonómicos. Los mapas resultantes son imágenes raster en PNG que se insertan en el Documento Ambiental y quedan registradas en `capas/cartografia_trace.json`.

Esta especificación define el estándar único de calidad: qué debe contener cada mapa, cómo debe pedirse, qué fallbacks usar cuando un servicio falla, y qué mínimo de calidad es aceptable para un DA administrativamente válido.

---

## 2. Estándar técnico de salida

### 2.1 Formato y resolución

| Parámetro | Valor estándar | Notas |
|-----------|---------------|-------|
| Formato preferido | PNG (RGB, 8 bits) | Sin compresión con pérdida |
| Formato alternativo | JPEG | Solo cuando el servidor no admite PNG (ej. GRAFCAN OrtoExpress) |
| Resolución objetivo (producción final) | 300 DPI en A4 | Equivale a ≈ 2480×1748 px para A4 apaisado — estándar para DA presentado |
| Resolución mínima (test / piloto) | 150 DPI en A4 | Equivale a ≈ 1240×874 px para A4 apaisado — válido solo en modo `--test` |
| Dimensiones mínimas | 800 px en lado corto | Para todos los mapas |
| Dimensiones recomendadas | 1000×700 a 1200×1000 px | Según tipo (ver tabla §4) |
| Espacio de color | RGB | No CMYK en salida automática |
| Fondo transparente | No | Fondo blanco siempre |

> **Nota de registro**: cuando el servidor devuelve JPEG con extensión `.png`, registrar en `cartografia_trace.json` el campo `formato` con el valor real: `"JPEG (extensión .png — contenido real JPEG por restricción del servidor)"`. No es un error, pero debe ser explícito.

### 2.2 Sistemas de referencia de coordenadas (CRS)

| Uso | CRS | EPSG | Cuándo |
|-----|-----|------|--------|
| Peticiones a servidores nacionales (IGN, MITECO, IGME) | WGS84 geográfico | 4326 | Siempre |
| Peticiones a GRAFCAN / IDECanarias | REGCAN95 UTM Huso 28N | 32628 | Preferente; fallback 4326 |
| Medición interna, bbox en metros | REGCAN95 UTM Huso 28N | 32628 | Control interno |
| Documentación de coordenadas del proyecto | WGS84 + REGCAN95 | 4326 + 32628 | Siempre ambos |

Regla: guardar `bbox_wgs84` y `bbox_utm28n` en cada CT aunque solo se haya usado uno para la petición.

### 2.3 Escala y bbox

**Escalas de referencia por tipo de mapa:**

| Tipo | Escala aprox. | Bbox característica |
|------|--------------|---------------------|
| Situación general (isla) | 1:80.000 – 1:120.000 | Lanzarote completo ± 5 km |
| Contexto municipal | 1:30.000 – 1:50.000 | Municipio + entorno 5 km |
| Ortofoto de detalle | 1:2.000 – 1:5.000 | Proyecto + 500–1000 m buffer |
| Parcela catastral | 1:1.000 – 1:3.000 | Proyecto + 200 m buffer |
| Temáticos regionales (RN2000, ENP) | 1:200.000 – 1:400.000 | Isla completa |
| Temáticos de media escala (inundabilidad) | 1:30.000 – 1:60.000 | Municipio + cuenca |
| Temáticos geológicos | 1:100.000 – 1:200.000 | Isla o sector geológico |

**Regla de buffer para bbox:**
- Mapas de detalle (ortofoto, catastral): buffer de al menos 500 m alrededor del polígono del proyecto.
- Mapas de contexto regional: usar bboxes predefinidas por isla (ver §6) — no centrar en el proyecto.
- Nunca usar una bbox tan pequeña que el servidor devuelva imagen vacía o corrupta. Si la petición devuelve < 10 KB, sospechar imagen vacía y ampliar bbox.

### 2.4 Elementos cartográficos obligatorios

Todo mapa generado por AG-06 debe incluir o documentar la ausencia justificada de:

| Elemento | Obligatorio | Formato aceptable |
|----------|-------------|-------------------|
| Título descriptivo | **Sí — AG-06** | En `cartografia_trace.json` campo `titulo` |
| Marcador del proyecto (punto o polígono) | **Sí — AG-06** | Punto rojo (mapas regionales) o polígono con borde rojo (localización precisa) — ver §2.5 |
| Escala numérica | **Sí — AG-06** | En `cartografia_trace.json` campo `escala_aprox` |
| Barra de escala | **Sí — AG-06** | En la imagen o pendiente para M-11 con nota explícita en CT |
| Rosa de los vientos / flecha norte | **Sí — AG-06** | En la imagen o pendiente para M-11 con nota explícita en CT |
| Fuente y fecha del servicio | **Sí — AG-06** | En `cartografia_trace.json` campo `servicio.datos_actualizacion` |
| Leyenda temática | Obligatoria en temáticos | CORINE, Red Natura, ENP, inundabilidad, geología |
| CRS usado en la petición | Sí | En `cartografia_trace.json` campo `CRS_peticion` |
| Fecha de descarga | Sí | En `cartografia_trace.json` campo `fecha_descarga` |

> **Requisitos propios de AG-06**: norte, escala, fuente/fecha y marcador/polígono son responsabilidad directa de este agente. Si cualquiera de ellos falta en la imagen descargada, debe quedar pendiente para M-11 con nota obligatoria en el CT. Un mapa sin marcador/polígono correcto tiene estado **PROVISIONAL**, no VALIDADO (ver §2.5 y §7).

> **Advertencia sobre leyendas**: los servicios WMS estándar no incluyen leyenda en la imagen raster. La leyenda debe añadirse en la fase de maquetación (M-11) o incorporarse como imagen separada. AG-06 no puede generar leyendas automáticamente, pero debe advertirlo en `notas` de cada CT cuando el mapa lo requiera.

### 2.5 Marcador del proyecto

| Tipo de mapa | Marcador requerido | Estado sin marcador correcto |
|-------------|-------------------|------------------------------|
| Localización precisa (MAP-001, MAP-002, MAP-003) | **Polígono o delimitación obligatoria** — borde rojo 2px, relleno amarillo 50% | **PROVISIONAL** — no VALIDADO |
| Contexto ambiental regional (MAP-004, MAP-005, MAP-007, MAP-008) | **Punto del proyecto obligatorio** — círculo rojo visible | **PROVISIONAL** — no VALIDADO |
| Restricciones de escala media (MAP-006) | Punto del proyecto + referencia a límite municipal | **PROVISIONAL** si falta |

**Regla de estado**: un mapa sin marcador/polígono correcto es **PROVISIONAL**. Solo pasa a **VALIDADO** cuando el marcador está incorporado (en la imagen descargada o en la composición M-11). Registrar `"estado_marcador": "INCLUIDO | PENDIENTE_M11"` en el CT.

El marcador se superpone siempre sobre la imagen del WMS. En la arquitectura actual (descarga HTTP directa) la superposición requiere un paso de composición posterior. AG-06 registra en `cartografia_trace.json` si el marcador está incluido en la imagen o pendiente para M-11.

### 2.6 Colores y estilo base

| Elemento | Color / estilo |
|----------|---------------|
| Polígono del proyecto | Borde: #CC0000 (rojo) 2px; Relleno: #FFAA00 50% alfa |
| Punto del proyecto | #CC0000 círculo sólido |
| Espacios Red Natura 2000 | Verde oscuro #2E6B2E; relleno #A8D5A2 40% |
| ENP (distinción por categoría) | Según leyenda MITECO (no modificar colores oficiales) |
| Zonas inundables | Azul claro #87CEEB (T500) a azul intenso #0000CD (T10) |
| Base topográfica | Sin modificación (colores IGN/GRAFCAN nativos) |
| Base ortofoto | Sin modificación (imagen real) |
| Base catastral | Sin modificación (colores Catastro nativos) |

---

## 3. Clasificación de mapas por función

### 3.1 Mapas de localización

Objetivo: situar geográficamente el proyecto para el lector del DA. El órgano ambiental necesita entender dónde está el proyecto antes de leer cualquier análisis.

| ID | Denominación | Escala | Base | Obligatorio |
|----|-------------|--------|------|-------------|
| MAP-001 | Situación general | 1:80.000 – 1:120.000 | IGN MTN rasterizado | Sí |
| MAP-002 | Parcela catastral | 1:1.000 – 1:3.000 | Catastro INSPIRE | Sí |
| MAP-003 | Ortofoto de detalle | 1:2.000 – 1:5.000 | GRAFCAN OrtoExpress | Sí |

### 3.2 Mapas de contexto ambiental

Objetivo: caracterizar el entorno ambiental del proyecto para fundamentar el inventario de Fase 5.

| ID | Denominación | Escala | Base | Obligatorio |
|----|-------------|--------|------|-------------|
| MAP-004 | Red Natura 2000 | 1:200.000 – 1:400.000 | MITECO + IGN | Sí |
| MAP-005 | ENP (Espacios Naturales Protegidos) | 1:200.000 – 1:400.000 | MITECO + IGN | Sí |

### 3.3 Mapas temáticos de restricciones

Objetivo: identificar restricciones legales o físicas que afectan al emplazamiento.

| ID | Denominación | Escala | Base | Obligatorio |
|----|-------------|--------|------|-------------|
| MAP-006 | Zonas inundables | 1:30.000 – 1:60.000 | IDECanarias RIESGOMAP | Sí (Canarias) |
| MAP-007 | Geología / Litología | 1:100.000 – 1:200.000 | IGME o IDECanarias | Sí |
| MAP-008 | Usos del suelo | 1:100.000 – 1:200.000 | CORINE o SIOSE | Sí |

### 3.4 Mapas opcionales o condicionados

| Denominación | Cuándo incluir | Fuente sugerida |
|-------------|---------------|-----------------|
| Patrimonio arqueológico | Si hay BICs o zonas de cautela arqueológica próximas | INTBIC (IGN/MITECO) |
| Dominio Público Hidráulico | Si la instalación está próxima a cauces | CHC / IDECanarias |
| Dominio Público Marítimo-Terrestre | Si hay franja costera en el radio de influencia | MITECO DPMT |
| Planeamiento urbanístico | Compatibilidad urbanística (Fase 4) | Municipio o GRAFCAN |
| Vías pecuarias | Si hay vías pecuarias afectadas | MITECO VP WMS |

---

## 4. Estándar por tipo de mapa (tabla de referencia)

| Mapa | Dimensiones recomendadas (px) | CRS petición | Fuente primaria | Fallback |
|------|------------------------------|--------------|-----------------|---------|
| MAP-001 Situación general | 1000 × 700 | EPSG:4326 | IGN MTN rasterizado | IGN Base | 
| MAP-002 Parcela catastral | 800 × 700 | EPSG:4326 (WMS 1.1.1 lon,lat) | Catastro INSPIRE | Catastro WMTS |
| MAP-003 Ortofoto detalle | 1200 × 1000 | EPSG:32628 | GRAFCAN OrtoExpress | IGN PNOA (si disponible Canarias) |
| MAP-004 Red Natura 2000 | 900 × 900 | EPSG:4326 | MITECO RN2000 WMS | Shapefile MITECO descarga + composición manual |
| MAP-005 ENP | 900 × 900 | EPSG:4326 | MITECO ENP WMS | Shapefile MITECO descarga + composición manual |
| MAP-006 Zonas inundables | 900 × 1000 | EPSG:32628 | IDECanarias RIESGOMAP | PGRI Lanzarote (datos descarga) |
| MAP-007 Geología | 900 × 750 | EPSG:4326 | IDECanarias Geología | IGME Geológico 1M (limitado) |
| MAP-008 Usos del suelo | 1000 × 700 | EPSG:4326 | Copernicus CORINE 2018 | SIOSE IDECanarias |

---

## 5. Catálogo de servicios WMS — Canarias

### 5.1 Servicios operativos (verificados en piloto RECIMETAL, 2026-04-12)

| ID | Servicio | URL base | Versión | Estado | Notas |
|----|---------|----------|---------|--------|-------|
| SRV-001 | Catastro INSPIRE (WMS) | `https://ovc.catastro.meh.es/cartografia/INSPIRE/spadgcwms.aspx` | 1.1.1 | OPERATIVO | Usar WMS 1.1.1 (bbox lon,lat); cubre Canarias |
| SRV-002 | GRAFCAN OrtoExpress (WMS) | `https://idecan1.grafcan.es/ServicioWMS/OrtoExpress` | 1.3.0 | OPERATIVO | Solo imagen/jpeg; extensión .png engañosa |
| SRV-005-ALT | IDECanarias RIESGOMAP (WMS) | `https://idecan1.grafcan.es/ServicioWMS/RIESGOMAP` | 1.3.0 | OPERATIVO | Canarias — capas: RT_INUNDACION_FLUVIAL, RT_INUNDACION_COSTERA |
| SRV-006 | Copernicus CORINE 2018 (MapServer) | `https://copernicus.discomap.eea.europa.eu/arcgis/rest/services/Corine/CLC2018_WM/MapServer` | ArcGIS REST | OPERATIVO | API export; sin leyenda en imagen |
| SRV-007 | IGN MTN Rasterizado (WMS) | `https://www.ign.es/wms-inspire/mapa-raster` | 1.3.0 | OPERATIVO | Capa: mtn_rasterizado; cubre Canarias |
| SRV-008 | MITECO ENP (WMS) | `https://wms.mapama.gob.es/sig/Biodiversidad/ENP/wms.aspx` | 1.3.0 | OPERATIVO | Capa: PS.ProtectedSite |

### 5.2 Servicios con incidencias conocidas

| ID | Servicio | Problema | Fallback obligatorio |
|----|---------|----------|---------------------|
| SRV-003 | MITECO Red Natura 2000 (WMS GetMap) | IndexOutOfRange con bboxes pequeñas | Usar bbox de isla completa; si falla: shapefiles MITECO |
| SRV-004 | IGME Litológico/Geológico 1M | Imagen PNG corrupta o inválida para Canarias | IDECanarias Mapa Geológico |
| SRV-005 | SNCZI IDEE Inundaciones | No cubre Canarias (demarcación peninsular) | **Nunca usar para Canarias** — usar RIESGOMAP IDECanarias |

### 5.3 Fallback geológico confirmado (IDECanarias)

| ID | Servicio | URL base | Estado | Limitación |
|----|---------|----------|--------|-----------|
| SRV-GEO-OK | IDECanarias Mapa Geológico (WMS) — **nodo idecan2** | `https://idecan2.grafcan.es/ServicioWMS/Geologico` | **USABLE** — confirmado como fallback operativo | Verificar escala disponible; si es ≥ 1:100.000, aceptable para MAP-007; si solo 1:1M, registrar limitación y crear GAP MEDIA |
| SRV-GEO-KO | IDECanarias GeologiaCanarias (WMS) — nodo idecan1 | `https://idecan1.grafcan.es/ServicioWMS/GeologiaCanarias` | **DESCARTADO** — endpoint no responde | No usar |

> **Regla**: MAP-007 usa primero IGME Geológico 1M; si falla o la escala es insuficiente, usar `idecan2.grafcan.es/ServicioWMS/Geologico`. El endpoint de idecan1 GeologiaCanarias queda descartado.

### 5.4 Servicios pendientes de verificación

| Servicio | URL tentativa | Prioridad |
|---------|--------------|-----------|
| IDECanarias SIOSE (WMS) | Portal IDECanarias — verificar endpoint | MEDIA (fallback MAP-008) |
| MITECO Red Natura 2000 (descarga shapefile) | `https://www.miteco.gob.es/es/biodiversidad/servicios/banco-datos-naturaleza/` | MEDIA |
| IGN Base (WMS) | `https://www.ign.es/wms-inspire/ign-base` | BAJA (alternativa MAP-001) |

### 5.4 Bboxes predefinidas por isla (WGS84)

| Isla | oeste | sur | este | norte | Uso |
|------|-------|-----|------|-------|-----|
| Lanzarote | -14.10 | 28.65 | -13.25 | 29.50 | Mapas regionales (RN2000, ENP) |
| Lanzarote + Arrecife | -13.70 | 28.92 | -13.40 | 29.04 | Situación general |
| Gran Canaria | -15.90 | 27.65 | -15.25 | 28.25 | Mapas regionales GC |
| Tenerife | -16.95 | 27.95 | -16.05 | 28.65 | Mapas regionales TF |
| Fuerteventura | -14.60 | 27.90 | -13.70 | 28.80 | Mapas regionales FV |

---

## 6. Lecciones del piloto RECIMETAL para AG-06

### 6.1 Fuentes que funcionaron correctamente

**IGN MTN rasterizado (MAP-001)**: servicio estable, cubre toda España incluyendo Canarias, calidad visual alta para situación general. Dimensiones 1000×700 produjeron resultado óptimo (722 KB — imagen rica). **Patrón validado: usar siempre para MAP-001.**

**GRAFCAN OrtoExpress (MAP-003)**: servicio operativo con resolución 10 cm/pixel (vuelo 2024). CRS nativo REGCAN95 UTM 28N. Imagen de 267 KB confirmó ubicación en Polígono Industrial de Tenorio. Incidencia menor: no admite `image/png`, devuelve JPEG con extensión `.png`. **Patrón validado: usar siempre para MAP-003; registrar formato real en CT.**

**Catastro INSPIRE (MAP-002)**: servicio operativo. Requiere WMS 1.1.1 (no 1.3.0) para bbox en orden lon,lat. Imagen resultante de 4,1 KB generó cautela (posible imagen casi vacía en zona industrial con pocas edificaciones). **Patrón validado: verificar tamaño del archivo — si < 8 KB, ampliar bbox y regenerar.**

**IDECanarias RIESGOMAP (MAP-006)**: fuente correcta para inundabilidad en Canarias. El SNCZI estatal NO cubre Canarias. Esta regla es no negociable. Imagen de 11 KB (poca cartografía de riesgo en la zona) es un resultado válido — no indica error. **Patrón validado: único servicio correcto para inundabilidad en Canarias.**

**MITECO ENP (MAP-005)**: servicio estable para ENP. Mismo endpoint base que Red Natura pero distinto path. Imagen de 13 KB con bbox de isla. Resultado válido.

### 6.2 Fuentes con problemas y sus resoluciones

**MITECO Red Natura 2000 — GetMap falla con IndexOutOfRange:**
- Causa: el servicio falla cuando la bbox es pequeña (proyecto o municipio). No es un fallo total del servicio.
- Solución aplicada en piloto: usar bbox de isla completa (Lanzarote: -14.10, 28.65, -13.25, 29.50). Imagen de 44 KB con esta bbox. Resultado correcto.
- Regla para AG-06: **siempre usar bbox de isla para RN2000 y ENP, nunca bbox de proyecto.**
- Si persiste el fallo: usar shapefiles de descarga del MITECO como fallback (CT con estado REFERENCIADO + nota de fallback).

**IGME Litológico 1M — imagen PNG corrupta:**
- Causa: el servicio IGME litológico devuelve datos no válidos para Canarias a esta escala.
- El servicio Geológico 1M (usado en MAP-007) funcionó y produjo imagen válida de 12 KB, aunque con limitación de escala insuficiente.
- Fallback obligatorio para detalle: **IDECanarias Mapa Geológico** (endpoint a verificar antes del primer expediente real).
- Regla para AG-06: registrar siempre la limitación de escala del IGME 1M. Para expedientes que requieran detalle litológico, escalar a GAP con criticidad MEDIA.

**SNCZI IDEE inundaciones — no cubre Canarias:**
- Causa sistémica: el SNCZI está restringido a demarcaciones hidrográficas peninsulares e insulares (no incluye demarcaciones canarias en el WMS).
- Esta incidencia es permanente, no temporal.
- Regla para AG-06: **nunca intentar SNCZI para Canarias.** Arrancar directamente con IDECanarias RIESGOMAP. Documentar en CT el motivo.

**Leyenda CORINE no integrada en imagen (MAP-008):**
- El servicio ArcGIS MapServer de Copernicus no incluye leyenda en la imagen exportada.
- Impacto: el mapa no es autónomo sin leyenda.
- Solución en AG-06: registrar `"leyenda_pendiente": true` en CT-008 y añadir a lista de pendientes para M-11.
- Para el expediente real: usar leyenda oficial CORINE descargada del portal Copernicus.

### 6.3 Hallazgos de diseño del piloto

**Tamaño del archivo como indicador de calidad:**
Imágenes < 10 KB en mapas que deberían tener contenido son señal de alerta. Umbrales orientativos:
- MAP-001 (MTN): esperado > 300 KB; < 100 KB → sospecha de imagen vacía
- MAP-002 (catastral): puede ser < 10 KB en zonas industriales poco edificadas — aceptable con cautela
- MAP-003 (ortofoto): esperado > 100 KB; < 50 KB → probable error o bbox vacía
- MAP-004/005 (RN2000/ENP): puede ser < 50 KB si la zona tiene poca cobertura temática — aceptable

**Verificación cartográfica CT-009 como paso separado:**
El piloto incluyó CT-009 como verificación de coherencia de coordenadas (WGS84 ↔ UTM). Esta verificación no produce archivo raster pero cierra el HC de coordenadas. Es un paso de control interno, no un mapa. Debe mantenerse como tipo `VERIFICACION_INTERNA` en cartografia_trace.json.

**Formato JPEG vs PNG:**
GRAFCAN no admite `image/png`. El piloto usó formato JPEG con extensión `.png`. Aunque funciona, puede confundir herramientas que leen el formato por extensión. Para el sistema productivo: guardar con extensión `.jpg` cuando el contenido sea JPEG, y registrar en CT el campo `formato` con el valor correcto.

---

## 7. Criterios de aceptación de cada mapa

Un mapa es ACEPTADO para el expediente si cumple todos los criterios de su tipo:

| Criterio | Localización | Contexto | Temático restricciones |
|----------|-------------|---------|----------------------|
| Archivo existe en `mapas/` | Sí | Sí | Sí |
| Tamaño > umbral mínimo | Sí | Sí | Sí |
| CT registrado en `cartografia_trace.json` | Sí | Sí | Sí |
| CRS documentado | Sí | Sí | Sí |
| Fecha de descarga registrada | Sí | Sí | Sí |
| Servicio fuente identificado | Sí | Sí | Sí |
| Marcador proyecto incluido o pendiente M-11 | Sí | Sí | Recomendado |
| Leyenda incluida o pendiente M-11 | N/A | N/A | Sí |
| Limitaciones documentadas en `notas` | Si las hay | Si las hay | Si las hay |

Un mapa con estado `FALLBACK` (servicio primario falló, se usó alternativa) es aceptable si:
- El CT documenta el fallo del servicio primario.
- El CT documenta el servicio alternativo usado.
- La imagen resultante tiene tamaño > umbral mínimo.

Un mapa con estado `PROVISIONAL` tiene imagen descargada pero le falta algún requisito propio de AG-06 (marcador/polígono, norte, escala o fuente/fecha). Es aceptable para avanzar solo si:
- El CT documenta qué elemento falta y que queda pendiente para M-11.
- El campo `estado_marcador` indica `"PENDIENTE_M11"`.
- M-11 cierra el pendiente antes del ensamblaje final.

Un mapa con estado `PENDIENTE` (sin imagen) bloquea el gate de Fase 4 en producción. En modo `--test` genera WARNING, no ERROR.

---

## 8. Integración con el validador (EN-02 / validate_expediente.py)

AG-06 produce entradas en `cartografia_trace.json`. El validador EN-02 verifica que:
- Cada CT con `archivo_resultado` distinto de `"N/A"` tiene el archivo físico en la ruta indicada.
- Los CT de tipo `VERIFICACION_INTERNA` con `archivo_resultado = "N/A"` no son bloqueantes.
- CTs con estado `PENDIENTE` generan WARNING (no ERROR) en modo `--test`.

Para que los mapas pasen EN-02, los archivos deben estar en `mapas/` con el nombre exacto registrado en `archivo_resultado` del CT correspondiente.

---

*Especificación generada por EIA-Agent v2.1 — Productización P2 — 2026-04-15*
