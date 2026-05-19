# Especificación metodológica — AG-10 / Bloque G
## Análisis de Vulnerabilidad ante Accidentes Graves y Catástrofes Naturales

**Versión**: 2.1  
**Estado**: VALIDADO  
**Fecha**: 2026-04-16  
**Baseline**: piloto EIA-2026-RECIMETAL-PARCELA  

---

## §1. Qué es un Bloque G válido en este sistema

El Bloque G analiza la vulnerabilidad del proyecto ante amenazas externas — naturales, climáticas y tecnológicas del entorno. No es un análisis de los impactos del proyecto sobre el medio (eso es Bloque C). Es la dirección inversa: qué le puede hacer el medio al proyecto, y qué consecuencias ambientales y de seguridad tendría eso.

Un Bloque G válido cumple cinco condiciones:

1. **Bidireccional en concepto, no confundido**: distingue claramente entre (a) cómo las amenazas externas afectan al proyecto y (b) cómo el proyecto, afectado por esas amenazas, podría convertirse en fuente de impacto ambiental secundario o accidente. La segunda dirección es la que justifica la presencia del Bloque G en el DA.

2. **Basado en datos disponibles, no en supuestos genéricos**: los riesgos naturales se evalúan con los datos de AG-07 (climáticos), AG-06 (cartografía) y las fichas de riesgo natural de AG-08. Un bloque que evalúa riesgos sin referenciar datos concretos del expediente es texto de plantilla.

3. **Proporcionado a la naturaleza del proyecto**: una instalación de almacenamiento manual de residuos no peligrosos no requiere el mismo nivel de análisis que una planta química. La proporcionalidad es un criterio explícito del Anexo VI Ley 21/2013.

4. **Transparente sobre limitaciones**: si un riesgo no puede evaluarse bien en modo gabinete (sismicidad local, riesgo volcánico zonal, instalaciones vecinas con materiales peligrosos), se declara la limitación con el estado de evidencia correspondiente. No se descarta sin análisis.

5. **Conectado hacia atrás**: los riesgos naturales relevantes que ya han sido incorporados como impactos en Bloque C (ej: viento → IMP-01) se referencian explícitamente en Bloque G. La coherencia entre G.2 y C.3 es auditable.

---

## §2. Marco conceptual: las dos direcciones del Bloque G

### Dirección 1: amenaza → proyecto
¿Cómo puede una catástrofe natural o un accidente externo afectar al proyecto?

- ¿La instalación es físicamente vulnerable a inundaciones, viento extremo, seísmos?
- ¿Podría una catástrofe natural dañar infraestructuras de la instalación (solera, arquetas, acopios)?
- ¿Podría el cambio climático aumentar la frecuencia o intensidad de las amenazas relevantes?

### Dirección 2: proyecto afectado → entorno
Si la amenaza afecta al proyecto, ¿podría el proyecto convertirse en fuente de daño ambiental o accidente?

- ¿Podría un viento extremo dispersar materiales peligrosos o contaminantes del proyecto hacia el entorno?
- ¿Podría una inundación arrastrar contaminantes de la instalación hacia la red de drenaje?
- ¿Podría un incendio en la instalación generar emisiones tóxicas o afectar instalaciones vecinas?
- ¿Podría una avería de la instalación convertirse en un accidente de mayor escala por efecto dominó?

**La segunda dirección es la que el Bloque G debe analizar con mayor profundidad**, porque es la que justifica su presencia en el Documento Ambiental desde el punto de vista de la Ley 21/2013. La primera es el contexto que hace relevante la segunda.

---

## §3. Categorías de riesgo obligatorias

Para cualquier expediente en España, el redactor del Bloque G verifica estas categorías. Si el riesgo es irrelevante para la tipología y ubicación del proyecto, se declara explícitamente como "No relevante para este proyecto — [razón]", no se omite en silencio.

| Categoría | Fuentes de datos del sistema | Threshold de relevancia |
|-----------|-----------------------------|-----------------------|
| **Viento extremo** | AG-07 (AEMET: días/año >umbral, velocidades máximas), MAP-006 (exposición cartográfica) | Siempre relevante en instalaciones con materiales sueltos o a cielo abierto |
| **Precipitación torrencial / inundación** | AG-07 (P_máx 24h), AG-06 (MAP-006 PGRI, IDECanarias o SNCZI según CC.AA.), fichas FI-riesgos | Relevante en instalaciones con suelos impermeabilizados, drenaje o líquidos |
| **Calima / polvo sahariano** | AG-07 (episodios documentados) | Relevante en Canarias y sur de la Península; actúa como amplificador del IMP de calidad del aire |
| **Sequía** | AG-07 (Martonne, déficit hídrico) | Relevante si hay procesos que consumen agua (humectación, extinción de incendios) |
| **Sismicidad** | IGN (mapa de peligrosidad sísmica), NCSE-02 | Siempre verificar; relevante si hay estructuras frágiles o materiales que podrían dispersarse |
| **Riesgo volcánico** | IGN (ZVC, IRV), IGME | Solo en Canarias (Tenerife, La Palma, El Hierro, Lanzarote, Fuerteventura) y zonas geológicamente activas |
| **Incendio** | Compatibilidad de materiales almacenados con combustión; contexto urbanístico (polígono vs interface urbano-forestal) | Siempre verificar; relevante si hay materiales orgánicos, inflamables o fuentes de ignición |
| **Accidente tecnológico externo** | Registro de establecimientos Seveso en el entorno (ENAC / ministerio); distancia a instalaciones con sustancias peligrosas | Relevante si la instalación está en polígono industrial con vecinos de alto riesgo |
| **Cambio climático** | Ley 6/2022 (Canarias) o normativa autonómica + IPCC; AG-07 (tendencias) | Siempre incluir — análisis de cómo las tendencias proyectadas afectan a las amenazas anteriores |

---

## §4. Relación AG-06 / AG-07 / AG-08 → Bloque G

El Bloque G no genera datos propios. Los toma de:

| Fuente | Qué aporta al Bloque G |
|--------|------------------------|
| `clima/datos_climaticos.json` (AG-07) | Velocidades de viento, días de viento fuerte, precipitación máxima, episodios de calima, clasificación climática |
| `capas/cartografia_trace.json` + MAP-006 (AG-06) | Zonificación de inundabilidad (PGRI), zona de peligrosidad sísmica cartografiada, distancias a instalaciones Seveso |
| `fichas_inventario/FI-16_riesgos_naturales.json` (AG-08) | Síntesis de riesgos naturales con estado de evidencia y gaps |
| `capas/hechos_confirmados.json` | Naturaleza de los materiales almacenados (no peligrosos/peligrosos), presencia de procesos térmicos, equipos de energía |
| `capas/normativa_aplicable.json` | Sujeción o no a RD 840/2015 (Seveso III), normativa de protección civil aplicable |

**Antes de redactar G.2**: leer las fichas FI-16 de AG-08 y los datos climatológicos de AG-07. No evaluar riesgos naturales de memoria.

**Coherencia con Bloque C**: los riesgos naturales que ya generan impactos en Bloque C (viento → IMP-01, lluvia → IMP-03) deben referenciarse en G.2.1. Bloque G no los re-evalúa como impactos — solo confirma que ya están integrados en el análisis.

---

## §5. Cómo tratar cada categoría de riesgo

### Estructura estándar de análisis de cada riesgo

Para cada categoría, el análisis tiene tres partes:

**Exposición**: ¿cuánto está expuesto el proyecto a esta amenaza? (datos de AG-07 / AG-06)

**Vulnerabilidad**: ¿cuán vulnerable es la instalación específica a los efectos de esa amenaza? (tipo de construcción, materiales, operaciones)

**Consecuencia potencial**: si la amenaza se materializa sobre la instalación vulnerable, ¿qué pasaría desde el punto de vista ambiental y de seguridad?

Este esquema (exposición → vulnerabilidad → consecuencia) evita tanto la minimización ("no pasa nada") como el alarmismo ("catástrofe posible"). Lo que importa es la cadena de consecuencias, no la probabilidad absoluta.

### Incendio: tratamiento específico

El riesgo de incendio requiere dos sub-análisis:
1. **Iniciación interna**: ¿puede la instalación originar un incendio? (equipos eléctricos o térmicos, materiales inflamables, fuentes de ignición)
2. **Propagación desde el entorno**: ¿puede un incendio exterior afectar a la instalación?

En instalaciones de almacenamiento de residuos metálicos, el riesgo de iniciación es bajo (materiales inorgánicos) pero no nulo (equipos eléctricos, contaminación orgánica en residuos). La valoración "bajo" debe justificarse con referencia a los materiales concretos, no solo a la categoría general.

### Seveso III: tratamiento específico

La exclusión de Seveso III se declara con estado de evidencia INFERIDO si no hay análisis formal, o CONFIRMADO si hay consulta al Registro de Establecimientos Seveso. La exclusión nunca se da por supuesta en silencio.

Formulación correcta:
> "La instalación no está sujeta a la Directiva Seveso III (RD 840/2015) porque los materiales almacenados son residuos metálicos no peligrosos que no figuran en el Anexo I del RD 840/2015. [Estado: INFERIDO — no consta análisis formal de sujeción en los documentos del promotor]"

Formulación incorrecta:
> "La instalación no requiere análisis Seveso." (sin razón ni estado)

### Riesgo volcánico en Canarias

En Canarias, el riesgo volcánico es geológicamente real. La formulación correcta distingue:
- Riesgo a corto-medio plazo en la isla donde está el proyecto (estado sísmico/volcánico actual según IGN)
- Consecuencias potenciales para la instalación si ocurriera una erupción en la misma isla
- Si la isla es Lanzarote o Fuerteventura (último episodio histórico 1824): riesgo residual pero no descartable

No usar "volcán no activo" como argumento absoluto — ningún volcán de Canarias es declarado extinto.

### Cambio climático

El análisis de cambio climático no es un bloque de prospectiva libre — se basa en las proyecciones de la normativa de referencia:
- Canarias: Ley 6/2022 + DL 5/2024 + DL 1/2026, Plan de Adaptación de Canarias
- Resto de España: Plan Nacional de Adaptación (PNACC), IPCC AR6 para la región Mediterranean

La tabla de tendencias climáticas debe referenciar cuál es la fuente de cada tendencia proyectada, aunque sea una referencia a "IPCC AR6 proyecciones para el Mediterráneo / Canarias" o "evaluación de impactos del cambio climático en Canarias (MITECO)". Sin fuente, la tendencia es texto genérico.

---

## §6. Tratamiento de riesgos con evidencia limitada

En modo gabinete, varios riesgos no pueden evaluarse con precisión:

| Riesgo | Limitación típica en gabinete | Qué declarar |
|--------|-------------------------------|-------------|
| Inundación | Análisis visual de MAP-006; PGRI no consultado en detalle | "Bajo según cartografía disponible. Análisis detallado del PGRI pendiente (GAP-INV-XXX)" |
| Instalaciones Seveso vecinas | Sin consulta al Registro de Establecimientos | "No se han identificado establecimientos Seveso en el entorno inmediato según las fuentes consultadas. Confirmación requiere consulta al Registro nacional" |
| Suelos contaminados en parcela adyacente | Sin investigación de campo | "No consta información sobre suelos contaminados en el entorno. Consulta a SIGLO (registro de suelos contaminados) pendiente" |
| Riesgo sísmico detallado | Solo mapa de peligrosidad sísmica de escala nacional | "Zona de sismicidad [baja/media] según mapa IGN. Relevancia baja para esta tipología de instalación; sin análisis detallado de vulnerabilidad estructural" |

**Regla**: un riesgo con evidencia limitada recibe un nivel de valoración ESTIMADO con la limitación declarada. No recibe valoración BAJO sin declaración de la limitación. No desaparece del bloque.

---

## §7. Riesgo tecnológico del entorno: instalaciones vecinas

El Bloque G debe mencionar si el proyecto está en un polígono industrial o zona con instalaciones que puedan originar accidentes mayores. Si no hay información específica sobre instalaciones vecinas:

> "No se ha realizado consulta al Registro de Establecimientos Afectados por la normativa Seveso (RD 840/2015) en el entorno del polígono. En modo gabinete, no se han identificado instalaciones de alto riesgo tecnológico en las inmediaciones, pero esta verificación queda pendiente para el expediente real."

No sustituir esta declaración con silencio.

---

## §8. Modo test vs expediente real

| Aspecto | Modo test | Expediente real |
|---------|-----------|-----------------|
| PGRI / inundabilidad | Análisis visual de MAP-006; GAP abierto | Consulta detallada del PGRI con fichas de masa de agua y zona inundable |
| Instalaciones Seveso vecinas | Sin consulta al Registro | Consulta al Registro de Establecimientos Seveso |
| Sismicidad | Mapa de peligrosidad nacional (IGN) | Análisis de NCSE-02 para emplazamiento específico si hay estructuras relevantes |
| Tendencias climáticas | Referencia general a normativa; sin cuantificación | Cuantificación con escenarios RCP del IPCC para la región, si disponibles |
| Riesgo volcánico (Canarias) | Referencia a historial geológico IGN | Consulta a IGN (nivel de alerta volcánica actual) y PEVOLCA si aplica |

---

## §9. Estructura mínima obligatoria del Bloque G

```
G.1. Base normativa y justificación
     — art. 45 Ley 21/2013 (con referencia exacta)
     — proporcionalidad al tipo y escala del proyecto

G.2. Riesgos naturales
     G.2.1. Tabla de riesgos naturales (categoría / valoración / fuente / limitaciones)
     G.2.2. Interacción riesgos naturales — proyecto
             — referencia explícita a los IMPs ya analizados en Bloque C
             — mecanismo de transmisión riesgo → proyecto → impacto ambiental secundario

G.3. Riesgos de accidente grave y riesgo tecnológico
     G.3.1. Sujeción a Directiva Seveso III / RD 840/2015 (con estado de evidencia)
     G.3.2. Riesgo de incendio (con referencia a materiales concretos)
     G.3.3. Riesgo de derrame o contaminación accidental (si aplica)
     G.3.4. Riesgo tecnológico del entorno / instalaciones vecinas (o declaración de no consulta)
     G.3.5. Accidente laboral (solo: referencia a PRL; por qué no genera impacto ambiental nuclear)

G.4. Vulnerabilidad frente al cambio climático
     — tabla de tendencias con fuente
     — efecto sobre las amenazas relevantes del G.2
     — estado de evidencia global de la sección

G.5. Conclusión del análisis de vulnerabilidad
     — síntesis de los riesgos relevantes con sus valoraciones
     — estado general del análisis (ESTIMADO en modo gabinete)
     — no conclusión absoluta de "sin riesgo"
```

---

## §10. Lecciones del piloto RECIMETAL incorporadas

### Qué funcionó bien y debe protegerse

1. **Tabla G.2 con columna "Limitaciones"**: la cuarta columna que declara la fuente y las limitaciones de cada valoración es el elemento más valioso del bloque. Sin ella, la tabla se convierte en una lista de opiniones. Con ella, es auditable.

2. **GAP-INV-004 visible en la tabla**: el riesgo de inundación declarado como "BAJO según MAP-006" pero con el gap del PGRI abierto. Correcto y trazable.

3. **G.2.1 — Interacción riesgos-proyecto con referencias a IMPs**: "el riesgo de viento ha sido incorporado como IMP-01" es la conexión que hace coherente el DA. Debe estar en todos los expedientes.

4. **Declaración de no sujeción a Seveso con estado de evidencia**: "[Estado: INFERIDO — no consta análisis formal]" es más honesto que simplemente decir "no está sujeto". Modelo correcto.

5. **G.4 tabla de cambio climático**: incluir el vector de cambio climático con referencia a la Ley 6/2022 es metodológicamente correcto y obligatorio en Canarias.

### Riesgos detectados en el piloto (a corregir en siguiente expediente)

1. **Cambio climático sin referencia a fuente específica por fila**: la tabla G.4 usa "tendencia general en Canarias" como fuente de todas las filas. Sin una referencia más concreta (informe específico, escenario RCP, normativa de adaptación), esto es texto de plantilla. En el siguiente expediente: al menos citar el Plan de Adaptación de Canarias o la Ley 6/2022 con el artículo pertinente.

2. **Ausencia de análisis de instalaciones vecinas**: el piloto no tiene una sección sobre riesgo tecnológico del entorno. El Polígono Industrial de Tenorio podría tener instalaciones con materiales peligrosos adyacentes. Esta verificación está ausente. En el siguiente expediente: declarar explícitamente que se consultó (o que no se consultó) el Registro de Establecimientos Seveso.

3. **Incendio valorado como "bajo" solo por naturaleza inorgánica de residuos**: la valoración no analiza el riesgo de ignición por batería de la carretilla ni la posible presencia de fracciones orgánicas en residuos mixtos entrantes. En el siguiente expediente: el análisis del riesgo de incendio debe incluir las fuentes de ignición potenciales (equipos eléctricos, fluidos de vehículos), no solo la naturaleza de los materiales principales.

4. **"No se identifican riesgos de accidente grave ni de catástrofe"** en G.5: formulación excesivamente absoluta. El Bloque G sí identifica riesgos (viento, precipitación torrencial, incendio, derrame) — lo que dice es que no son de gran magnitud. La formulación correcta: "No se identifican riesgos de accidente grave de magnitud relevante, dada la naturaleza no peligrosa de los materiales y la ausencia de procesos térmicos o químicos."

5. **Riesgo volcánico tratado de forma muy breve**: "RESIDUAL — no cuantificable a corto plazo" sin referencia al estado de alerta volcánica del IGN para Lanzarote en el momento del expediente. Para un proyecto en Lanzarote, incluso con riesgo histórico bajo, merece una referencia al sistema de vigilancia del IGN.

---

*Especificación redactada en P2 — 2026-04-16*
