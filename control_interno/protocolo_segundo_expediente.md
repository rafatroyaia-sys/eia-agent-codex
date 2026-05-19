# Protocolo de test de generalización — Segundo expediente
## EIA-Agent v2.1 — Post-Productización 2

**Versión**: 1.0  
**Estado**: ACTIVO  
**Fecha**: 2026-04-16  
**Baseline de comparación**: piloto EIA-2026-RECIMETAL-PARCELA  

---

## §1. Objetivo del test

Verificar que el sistema EIA-Agent v2.1 es transferible a una tipología de proyecto distinta a la del piloto, detectar sobreajustes al caso RECIMETAL, e identificar los huecos que solo emergen fuera del contexto de "instalación industrial de almacenamiento de residuos metálicos en polígono de Lanzarote".

Este test no mide si el sistema produce un DA perfecto. Mide si el sistema produce un DA metodológicamente limpio, con las limitaciones correctamente declaradas, en un tipo de proyecto que no fue el de entrenamiento. Un DA que declara correctamente sus limitaciones y sus gaps es más valioso como test que un DA que parece completo pero oculta debilidades.

---

## §2. Perfil del expediente recomendado

### §2.1. Características que debe cumplir

1. **Procedimiento: EIA simplificada** — Anexo II Ley 21/2013. Mantiene el marco procedimental para que las diferencias observadas sean de tipología, no de procedimiento. Si el sistema funciona para EIA simplificada, eso es lo que se prueba.

2. **Sector diferente a residuos metálicos** — el inventario de impactos, los LER, las medidas y el PVA deben ser estructuralmente distintos para detectar dependencias ocultas.

3. **Componente biológico real** — el expediente piloto tenía biodiversidad casi nula (polígono industrial). El segundo expediente debe tener fauna o flora que requiera análisis de campo o al menos análisis de gabinete con bibliografía específica, para probar AG-08 en condiciones reales.

4. **Emplazamiento fuera del polígono industrial** — suelo rústico, agrícola o periurbano, para probar el triaje normativo con planeamiento urbanístico diferente y para probar la sección de alternativas de emplazamiento con más contenido real.

5. **Normativa autonómica diferente** — o bien Canarias con normativa sectorial distinta (energía, turismo, agroindustria), o bien Península (Andalucía, Extremadura, Castilla-La Mancha) para probar que el sistema no está hardcoded a normativa canaria.

6. **Al menos un impacto de significancia Moderado sin medidas** — para probar la cadena completa impacto relevante → medida correctora → seguimiento PVA → GAP si no hay datos suficientes. El piloto tenía todos los impactos en Compatible o Compatible residual.

7. **Promotor que haya aportado documentación técnica básica** — al menos una memoria descriptiva del proyecto. No hace falta un DA completo del promotor, pero sí suficiente para que AG-01/02/03 tengan material real que procesar.

### §2.2. Tipología recomendada: instalación fotovoltaica pequeña en suelo rústico

**Descripción**: instalación fotovoltaica de autoconsumo o pequeña generación (100–500 kWp), en parcela de suelo rústico agrícola, en cualquier CC.AA. peninsular o insular. Superficie entre 0,5 y 2 ha.

**Por qué es el segundo expediente ideal**:

| Dimensión | RECIMETAL (piloto) | FV en rústico (recomendado) |
|-----------|--------------------|-----------------------------|
| Sector | Gestión de residuos | Energía renovable |
| Suelo | Polígono industrial | Rústico agrícola |
| Biodiversidad | Casi nula | Posiblemente relevante (steppe birds, reptiles, flora arvense) |
| Natura 2000 | >12 km | Potencialmente cercano |
| Normativa sectorial | Ley 7/2022 (residuos) | RD 960/2020, normativa energética autonómica |
| LER codes | 13 fracciones | No aplica |
| Impactos | Polvo, ruido, drenaje | Terreno, fauna, visual, electromagnético |
| Alternativas reales | Ninguna (dependencia funcional) | Posibles alternativas de emplazamiento y orientación |
| Gestión de residuos | Es el objeto | Solo generación de pequeños residuos de construcción |
| Campo/gabinete | 100% gabinete | Campo necesario para fauna/flora |

**Señales que indicarían que este tipo funciona bien**:
- AG-08 genera fichas de fauna y flora con estado correcto (no inventa presencia/ausencia)
- AG-09 produce IMPs de fragmentación de hábitat, visual, fauna con cadena acción→factor→impacto coherente
- El Bloque H (Natura 2000) requiere análisis real, no la solución trivial del piloto
- El Bloque F (alternativas) puede analizar emplazamientos alternativos con más base documental

### §2.3. Segunda opción: actividad agroindustrial pequeña (almazara, bodega)

Si no se dispone de documentación FV, una almazara de aceite o bodega vitivinícola pequeña sirve como segunda opción. Añade: efluentes líquidos (alpechines, vinazas), olores, gestión de subproductos orgánicos, normativa de aguas y vertidos. Diferente de RECIMETAL pero en EIA simplificada.

### §2.4. Qué evitar en el segundo expediente

| Tipología | Por qué evitarla ahora |
|-----------|----------------------|
| Residuos metálicos (misma que RECIMETAL) | No prueba transferibilidad |
| Proyecto con Seveso III o materiales peligrosos | Añade complejidad que no está probada en los prompts |
| EIA ordinaria | Cambia el procedimiento — no es el test adecuado |
| Gran infraestructura (autovía, puerto, embalse) | Escala incompatible con el sistema actual |
| Proyecto muy urbano sin componente biológico | Demasiado similar a RECIMETAL en términos de inventario |
| Proyecto en entorno Natura 2000 solapado | El análisis de Bloque H se vuelve el eje central — no es el test correcto para generalización |

---

## §3. Módulos más sensibles al cambio de tipología

### Riesgo ALTO de sobreajuste a RECIMETAL

| Módulo | Qué puede fallar | Señal de alerta |
|--------|-----------------|-----------------|
| **AG-08 — Inventario** | Las 16 fichas FI están calibradas a "polígono industrial sin biodiversidad". En suelo rústico, FI-01 (flora), FI-02 (fauna), FI-03 (espacios naturales) necesitan mucho más contenido real y el sistema puede producir fichas genéricas o vacías. | La ficha FI-01 no tiene especies concretas aunque el emplazamiento esté en zona agrícola con potencial hábitat arvense |
| **AG-09 — Impactos** | Las cadenas acción→factor→impacto para instalación FV son completamente distintas (no hay polvo, no hay ruido de operación continua, pero hay fragmentación, visual, riesgo para fauna). El sistema puede intentar reutilizar cadenas de RECIMETAL que no aplican. | Aparece IMP de polvo en fase de operación de una instalación FV que no tiene movimiento de materiales |
| **AG-05 — Triaje normativo** | La normativa sectorial cambia completamente. Si el sistema cita Ley 7/2022 (residuos) en un expediente FV sin justificación, hay sobreajuste. | Aparece normativa de gestión de residuos en el encuadre legal de un proyecto de generación eléctrica |
| **bloque_F — Alternativas** | En RECIMETAL la alternativa de emplazamiento era trivial (dependencia funcional). En FV, puede haber alternativas reales de parcelas. El redactor puede resolver esta sección de forma igual de escueta que en RECIMETAL aunque ahora no esté justificado. | F.3 se resuelve con una frase y sin análisis cuando el proyecto en suelo rústico tiene parcelas alternativas identificables |

### Riesgo MODERADO de sobreajuste

| Módulo | Qué puede fallar | Señal de alerta |
|--------|-----------------|-----------------|
| **bloque_G — Vulnerabilidad** | El análisis de incendio en RECIMETAL partía de "materiales inorgánicos, bajo riesgo de iniciación". En FV, el riesgo de incendio por fallo de panel es un vector real diferente que el sistema puede no cubrir bien. | El análisis de incendio repite el argumento de "materiales inorgánicos" sin analizar el riesgo específico de instalaciones FV |
| **bloque_B — Inventario** | La narrativa puede estar calibrada a "biodiversidad mínima, sin flora ni fauna relevante". En suelo rústico puede necesitar más contenido y el redactor puede seguir el patrón de RECIMETAL. | Bloque B dice "no se detectan especies de interés en las fuentes consultadas" sin haber consultado el Catálogo de Flora Amenazada o el atlas de fauna para la zona |
| **bloque_H — Natura 2000** | En RECIMETAL era casi trivial (>12 km). Si el segundo expediente tiene un LIC/ZEC a 3 km, el análisis de "afección apreciable" se vuelve el núcleo del bloque, no un trámite. | Bloque H concluye "no se aprecia afección apreciable" con el mismo nivel de análisis que RECIMETAL aunque el espacio esté a 2 km |
| **AG-06 — Cartografía** | Los WMS del sistema están calibrados para Canarias (IDECanarias, GRAFCAN). Para proyectos peninsulares, algunos servicios deben cambiar (SNCZI en lugar de IDECanarias para inundabilidad, servicios del IGME para geología a escala adecuada). | El sistema intenta usar IDECanarias para un proyecto en Extremadura |

### Riesgo BAJO (probablemente transferible bien)

| Módulo | Por qué es más robusto | Verificar de todas formas |
|--------|----------------------|--------------------------|
| **AG-01 a AG-03 — Ingesta** | El parser y el clasificador de evidencia son tipología-agnósticos | Que los HCs se generen correctamente con documentación técnica FV |
| **AG-04 — Cierre del objeto** | La estructura de la ficha objeto evaluado es genérica | Que las operaciones y equipos FV se clasifiquen correctamente |
| **AG-07 — Clima** | AEMET funciona para cualquier emplazamiento estatal | Que la estación elegida sea la más próxima con series disponibles |
| **M-12 — Auditoría** | Los 9 ejes son independientes de tipología | Que los gaps de un expediente FV no provoquen falsos negativos en M-12 |
| **bloque_I — Conclusiones** | Las reglas anti-deriva son tipología-agnósticas | Que el redactor no añada menciones a gestión de residuos |
| **bloque_K — Referencias** | Derivado de JSONs — funciona si los JSONs son correctos | Que la normativa energética esté en normativa_aplicable.json |

---

## §4. Protocolo de ejecución fase a fase

### §4.1. Antes de empezar: configuración del test

Antes de ejecutar AG-01, documentar:
- Tipología exacta del proyecto
- CC.AA. del emplazamiento
- Procedimiento ambiental esperado (EIA simplificada / ordinaria)
- Qué documentos del promotor están disponibles
- Modo de inventario declarado (gabinete / campo / mixto)
- Qué gaps se anticipan respecto al piloto

Este registro es el punto de referencia para evaluar qué produjo el sistema vs qué se anticipaba.

---

### §4.2. Fase 1 — Ingesta (AG-01 + AG-02 + AG-03)

**Qué observar especialmente**:
- ¿AG-01 clasifica correctamente documentos técnicos de un sector diferente (memoria FV, proyecto técnico, estudio geotécnico si lo hay)?
- ¿AG-02 extrae HCs relevantes para la tipología FV? ¿Identifica potencia instalada, superficie, coordenadas, orientación?
- ¿AG-03 asigna estados de evidencia correctos? ¿No inflaciona CONFIRMADO para datos que son solo DECLARADOS?

**Señales de sobreajuste**:
- AG-02 intenta encontrar LER codes o capacidades de almacenamiento de residuos en un proyecto que no los tiene
- Los HCs generados tienen estructura interna que presupone operaciones de gestión de residuos
- AG-03 marca como PENDIENTE aspectos que para proyectos FV son normalmente DECLARADOS por el promotor

**Gate de Fase 1**: los HCs deben reflejar la tipología real del proyecto, no la del piloto. Si los HCs suenan a instalación de residuos, hay sobreajuste grave.

---

### §4.3. Fase 2 — Cierre del objeto (AG-04)

**Qué observar especialmente**:
- ¿La ficha del objeto incluye correctamente los equipos propios de FV (paneles, inversores, estructura de soporte, cableado, punto de conexión)?
- ¿Las fases del proyecto reflejan correctamente construcción / operación / desmantelamiento?
- ¿Las operaciones excluidas tienen sentido para una instalación FV?

**Señales de sobreajuste**:
- Aparecen campos específicos de gestión de residuos (báscula homologada, LER codes, gestor autorizado) en la ficha de una instalación FV
- Las fases del proyecto se describen en términos propios de una actividad industrial, no de una instalación de generación eléctrica

---

### §4.4. Fase 3 — Triaje normativo (AG-05)

**Qué observar especialmente**:
- ¿La normativa identificada es la correcta para el sector y la CC.AA.? Para FV: RD 960/2020 (sector eléctrico), normativa urbanística autonómica para instalaciones renovables, Ley del Sector Eléctrico.
- ¿El procedimiento ambiental identificado es correcto? ¿Se ha verificado el Anexo II correcto?
- ¿Las normas de gestión de residuos (Ley 7/2022) aparecen solo donde corresponde (gestión de residuos de construcción y desmantelamiento), no como marco general?

**Señales de sobreajuste**:
- Ley 7/2022 aparece como normativa principal del expediente en lugar de normativa energética
- Los artículos de la Ley 21/2013 citados corresponden al Grupo 9 (residuos) en lugar del Grupo correcto para el sector energético
- Normativa canaria específica citada para un proyecto peninsular sin adaptación

---

### §4.5. Fase 4 — Geodatos (AG-06 + AG-07)

**Qué observar especialmente**:
- **AG-06**: ¿el catálogo WMS funciona para emplazamiento peninsular? ¿Los servicios de IDECanarias se reemplazan correctamente por servicios estatales (SNCZI, IGN, SIGPAC)?
- **AG-07**: ¿la estación AEMET es la más representativa para el emplazamiento real? ¿La clasificación climática tiene sentido para el emplazamiento?
- **Cartografía de vegetación**: ¿el sistema intenta generar cartografía de flora/vegetación para la zona? En RECIMETAL esto era irrelevante; en suelo rústico es crítico.

**Señales de sobreajuste**:
- El sistema usa servicios de IDECanarias para un proyecto fuera de Canarias
- La cartografía generada no incluye mapas de vegetación o hábitats cuando el emplazamiento está en zona con biodiversidad potencial
- El climograma se genera para una estación inadecuada (ej: la más grande/famosa en lugar de la más próxima)

---

### §4.6. Fase 5 — Inventario (AG-08)

**Fase más sensible al cambio de tipología**.

**Qué observar especialmente**:
- ¿Las fichas FI-01 (flora) y FI-02 (fauna) tienen contenido real o son variaciones del texto genérico de RECIMETAL ("no se detectan especies de interés en las fuentes consultadas")?
- ¿El sistema consulta fuentes específicas para fauna y flora (BDN, GBIF, atlas de aves esteparias, catálogos de flora amenazada) o solo las fuentes cartográficas genéricas?
- ¿Las fichas FI-12 (geología/edafología) y FI-05 (hidrología) tienen contenido sustancialmente diferente al de RECIMETAL, dado que el suelo rústico tiene una caracterización edáfica distinta al polígono industrial?
- ¿Los semáforos de las fichas reflejan el nivel real de análisis, o el sistema replica los semáforos del piloto por defecto?

**Señales de sobreajuste más probables**:
- FI-01 concluye que no hay flora de interés sin haber consultado el catálogo de flora amenazada de la CC.AA.
- FI-02 concluye que no hay fauna de interés sin haber consultado el atlas de aves o reptiles para la zona
- Las fichas de factores sin relevancia en RECIMETAL (FI-07: suelo, FI-09: paisaje) están infradesarrolladas aunque sean centrales para una instalación FV en suelo rústico
- La ficha FI-09 (paisaje e impacto visual) tiene el mismo nivel de análisis que en RECIMETAL, donde era marginal

**Gate de Fase 5**: las fichas de biodiversidad deben tener estados de evidencia correctos. En modo gabinete para un emplazamiento en suelo rústico, el estado correcto para la mayoría de fichas de flora y fauna es INFERIDO_TECNICO o LIMITADO_ESCALA — no CONFIRMADO_GABINETE. Si el sistema genera CONFIRMADO_GABINETE para fauna sin consultas específicas a bases de datos de fauna, hay sobreajuste.

---

### §4.7. Fase 6 — Impactos, medidas y PVA (AG-09)

**Qué observar especialmente**:
- ¿Los impactos identificados son coherentes con la tipología FV? Impactos esperados: movimiento de tierras, fragmentación de hábitat, afección a fauna (aves, reptiles), impacto visual, afección a suelo, riesgo de incendio por fallo eléctrico. Impactos NO esperados: polvo de operación de carretilla, lixiviados de residuos metálicos.
- ¿El método Conesa simplificado funciona para valorar impactos visuales y de hábitat, que son cualitativos y más subjetivos que los impactos físico-químicos de RECIMETAL?
- ¿Las medidas son proporcionales y relevantes para FV? Medidas esperadas: revegetación de márgenes, protección de fauna durante obras, gestión de residuos de construcción, medidas de integración paisajística. NO esperadas: humectación de acopios de metal, vallado anti-polvo metálico.
- ¿El PVA tiene fichas con indicadores concretos para impactos cualitativos (paisaje, fauna)? Este es el punto más difícil — los indicadores para impacto visual y fragmentación de hábitat son menos operativos que los de PM10 o ruido.

**Señales de sobreajuste**:
- AG-09 produce un IMP-01 de "dispersión de partículas en fase de operación" cuando la instalación FV en operación no genera partículas
- Las medidas de control de polvo de RECIMETAL (M-01 cubrición, M-02 humectación) aparecen en una instalación sin movimiento de materiales en operación
- El PVA no tiene ficha de seguimiento para la fauna (específicamente aves y reptiles), que es el vector de impacto más relevante para FV

**Gate de Fase 6**: la lista de IMPs debe tener coherencia interna con la tipología. Si más del 30% de los IMPs identificados son idénticos en formulación a los de RECIMETAL, investigar si AG-09 está reutilizando el piloto como plantilla.

---

### §4.8. Fase 7 — Redacción (AG-10)

**Qué observar por bloque**:

| Bloque | Riesgo específico en segundo expediente |
|--------|----------------------------------------|
| A — Descripción | ¿Describe correctamente una instalación FV, o usa estructura y vocabulario de instalación de residuos? |
| B — Inventario | ¿Tiene contenido sustancialmente diferente para flora/fauna, o repite la estructura minimalista de RECIMETAL? |
| C — Impactos | ¿Los impactos redactados corresponden a los del JSON de AG-09, o hay deriva hacia impactos típicos de RECIMETAL? |
| F — Alternativas | ¿Analiza alternativas de emplazamiento con más profundidad que RECIMETAL dado que hay más opciones reales? ¿O resuelve F.3 igual de escuetamente? |
| G — Vulnerabilidad | ¿El análisis de incendio incluye el riesgo de fallo eléctrico en instalaciones FV, o usa solo el argumento de "materiales no inflamables"? |
| H — Natura 2000 | Si hay espacios cercanos, ¿el análisis es proporcional a la distancia real, o repite el análisis trivial de RECIMETAL? |
| I — Conclusiones | ¿Las conclusiones no mencionan gestión de residuos, LER codes ni operaciones R12/R13? |
| K — Referencias | ¿La normativa energética está en K.1? ¿No aparece Ley 7/2022 como normativa principal? |

---

### §4.9. Fase 9 — Auditoría (M-12)

**Qué observar especialmente**:
- ¿Los 9 ejes de M-12 producen calificaciones coherentes con lo observado en las fases anteriores?
- ¿M-12 detecta correctamente los sobreajustes tipológicos (impactos no coherentes, medidas de tipo RECIMETAL)?
- ¿El Eje 9 (calidad del PVA) detecta fichas sin indicadores concretos para impactos visuales o de fauna?
- ¿M-12 califica correctamente el estado general si hay gaps de biodiversidad no resueltos?

**Gate de Fase 9**: si M-12 produce CONFORME para un DA con sobreajustes evidentes de tipología, el sistema de auditoría tiene un problema de calibración que debe documentarse.

---

## §5. Lista de riesgos de sobreajuste a RECIMETAL

### Riesgos estructurales (afectan a múltiples agentes)

| ID | Riesgo | Agentes afectados | Probabilidad | Impacto |
|----|--------|-------------------|-------------|---------|
| RS-01 | El sistema usa "polígono industrial" como contexto implícito aunque el proyecto no esté en polígono | AG-08, AG-09, bloque_B, bloque_G | ALTA | ALTO |
| RS-02 | Los impactos de fase de operación se calibran a actividades intensivas de movimiento de materiales aunque el proyecto no las tenga | AG-09, bloque_C | MEDIA | ALTO |
| RS-03 | Las medidas correctoras se generan de un catálogo mental de "instalación de gestión de residuos" | AG-09, bloque_D | MEDIA | ALTO |
| RS-04 | La biodiversidad se trata como "baja por defecto" aunque el emplazamiento sea suelo rústico | AG-08, bloque_B | ALTA | ALTO |
| RS-05 | Los servicios WMS de IDECanarias se usan para proyectos peninsulares | AG-06 | MEDIA | MODERADO |

### Riesgos específicos de módulo

| ID | Riesgo | Módulo | Probabilidad |
|----|--------|--------|-------------|
| RS-06 | Ley 7/2022 aparece como normativa principal en sectores no relacionados con residuos | AG-05, bloque_K | MEDIA |
| RS-07 | F.3 (alternativas de emplazamiento) se resuelve con una frase aunque el emplazamiento tenga opciones reales | bloque_F | ALTA |
| RS-08 | El análisis de incendio de bloque_G usa solo el argumento de naturaleza del material sin analizar fuentes de ignición eléctricas | bloque_G | ALTA para FV |
| RS-09 | El bloque_H replica el análisis trivial de RECIMETAL aunque el espacio Natura 2000 esté más cerca | bloque_H | MEDIA |
| RS-10 | Las fichas PVA no tienen indicadores concretos para impactos visuales o de fauna | AG-09, bloque_E | ALTA |
| RS-11 | La nota de modo gabinete se usa para justificar fichas de flora/fauna vacías en lugar de declarar las limitaciones con estado correcto | AG-08, bloque_B | ALTA |
| RS-12 | La referencia a LER codes o operaciones R12/R13 aparece en algún bloque por inercia del entrenamiento | bloque_A, bloque_K | BAJA |

---

## §6. Criterios para considerar el test satisfactorio

### Criterios de pase (todos deben cumplirse)

| ID | Criterio | Cómo verificarlo |
|----|----------|-----------------|
| CP-01 | Los HCs generados por AG-01/02/03 reflejan la tipología correcta sin mencionar residuos metálicos ni operaciones R12/R13 | Revisión de `hechos_confirmados.json` |
| CP-02 | La normativa en `normativa_aplicable.json` es coherente con el sector del proyecto y la CC.AA. | Revisión del JSON + gate de Fase 3 |
| CP-03 | Las fichas FI-01 y FI-02 (flora/fauna) tienen estados de evidencia correctos — no CONFIRMADO sin fuente de campo o base de datos específica | Revisión de fichas AG-08 |
| CP-04 | La lista de IMPs de AG-09 no contiene impactos incoherentes con la tipología del proyecto | Revisión de `identificacion_valoracion_impactos.json` |
| CP-05 | Las medidas correctoras de AG-09 son coherentes con el tipo de proyecto y no son trasplantes de medidas de RECIMETAL | Revisión de `medidas_correctoras.json` |
| CP-06 | El Bloque F analiza las alternativas de emplazamiento con profundidad proporcional al número de opciones disponibles | Revisión de `bloques/F_alternativas.md` |
| CP-07 | El Bloque K no cita Ley 7/2022 como normativa principal si el proyecto no es de gestión de residuos | Revisión de `bloques/K_referencias.md` |
| CP-08 | M-12 produce una calificación coherente con los gaps y fortalezas observados | Revisión del informe de auditoría |

### Criterio de éxito global

El test es **satisfactorio** si se cumplen los 8 criterios de pase y los sobreajustes detectados son **recuperables mediante refactoring de prompts** sin necesidad de rediseñar la arquitectura de agentes.

El test es **parcialmente satisfactorio** si hay sobreajustes en 1-3 módulos que requieren refactoring de prompts pero la arquitectura global funciona.

El test es **insatisfactorio** si hay sobreajustes estructurales (RS-01 a RS-05) que afectan a múltiples agentes de forma sistémica, lo que indicaría que el problema está en SYSTEM_BASE o en la cadena de datos entre agentes, no en prompts individuales.

---

## §7. Qué hallazgos deben traducirse en refactor posterior

### Triggers para refactor de prompt individual

| Hallazgo | Prompt a refactor |
|----------|------------------|
| AG-08 genera fichas de flora/fauna genéricas sin consultar bases de datos específicas | AG-08_inventario.md — añadir regla de fuentes de biodiversidad obligatorias por tipo de emplazamiento |
| AG-09 genera IMPs incoherentes con la tipología | AG-09_impactos.md — añadir verificación de coherencia acción→impacto antes de validar la cadena |
| bloque_F resuelve alternativas de emplazamiento de forma igual de escueta en todos los casos | bloque_F_alternativas.md — añadir regla de proporcionalidad: a más opciones disponibles, más análisis requerido |
| bloque_G no analiza correctamente el riesgo de incendio en instalaciones eléctricas | bloque_G_vulnerabilidad.md — añadir sub-análisis específico para riesgo eléctrico |
| bloque_H replica análisis trivial aunque Natura 2000 esté cercano | bloque_H_natura2000.md — añadir regla de umbral de distancia: si <5 km, análisis ampliado obligatorio |

### Triggers para refactor de SYSTEM_BASE

| Hallazgo | Cambio recomendado en SYSTEM_BASE |
|----------|----------------------------------|
| El sistema usa "polígono industrial" como contexto implícito (RS-01) | Añadir regla de contexto-agnóstico: el tipo de emplazamiento se declara en AG-04 y no se puede asumir fuera de él |
| Normativa de residuos aparece en proyectos no relacionados (RS-06) | Añadir en SYSTEM_BASE la regla de pertinencia normativa: cada norma citada requiere vínculo explícito con el proyecto evaluado |

### Triggers para revisión de arquitectura (no solo prompts)

| Hallazgo | Revisión necesaria |
|----------|-------------------|
| Los datos de biodiversidad no pueden captarse en modo gabinete para ningún tipo de proyecto en suelo no industrial | Evaluar si AG-08 necesita un sub-agente especializado en biodiversidad con acceso a GBIF/BDN/REDIAM |
| Los indicadores de PVA para impactos cualitativos (visual, fauna) no pueden ser concretos en modo gabinete | Evaluar si el esquema PVA necesita una tipología de indicadores cualitativos estándar en AG-09 |
| AG-06 no funciona para proyectos fuera de Canarias sin intervención manual | Revisar el catálogo WMS de AG-06 para incluir fallbacks peninsulares en paridad con los canarios |

---

## §8. Registro del test

Este protocolo se completa con un registro de observaciones por fase a medida que se ejecuta el expediente. El registro se guarda en:

`control_interno/observaciones_segundo_expediente.md`

Formato del registro por fase:
```
## Fase X — [nombre de la fase]
**Fecha**: 
**Módulo**: 
**Observación**: [qué produjo el sistema]
**Tipo**: CORRECTO / SOBREAJUSTE / GAP_NO_CUBIERTO / MEJORA_POSIBLE
**Severidad**: ALTA / MODERADA / BAJA
**Acción recomendada**: [refactor de prompt / revisión arquitectura / aceptable en modo test]
```

---

*Protocolo redactado en P2 — 2026-04-16*
