# Especificación técnica — M-12: Auditoría final del expediente
**Versión**: 2.1  
**Estado**: VALIDADO  
**Fecha**: 2026-04-16  
**Baseline**: piloto-recimetal + criterios P2

---

## §1. Qué es una auditoría válida en este sistema

M-12 es el módulo de auditoría final del expediente EIA. Su función es doble:

1. **Control de calidad interno**: verificar que el expediente generado por los agentes AG-01 a AG-10 es internamente coherente, técnicamente sólido y formalmente completo antes de su presentación al órgano ambiental.
2. **Diagnóstico de madurez**: distinguir con precisión entre lo que el expediente puede acreditar (modo test), lo que necesita para ser presentable (expediente real), y si existe alguna incoherencia material que impida avanzar.

M-12 **no es**:
- El Informe de Impacto Ambiental (IIA) del órgano ambiental (art. 47 Ley 21/2013). El IIA lo formula el órgano ambiental.
- Una validación técnica del criterio del promotor. Verifica coherencia, trazabilidad y prudencia, no la corrección sustantiva de cada valoración de impacto.
- Un sustituto de la revisión jurídica del expediente en el marco del procedimiento formal.

### 1.1 Cuándo ejecutar M-12

M-12 se ejecuta una vez que todos los bloques del DA (A a K) y los outputs de AG-09 (impactos, medidas, PVA) están redactados. No se ejecuta durante la redacción — es una revisión ex post.

En un expediente real, M-12 debe ejecutarse antes del ensamblado final del DOCX (M-11). Si M-12 detecta incoherencias materiales, se corrigen antes de ensamblar. En modo test, puede ejecutarse sobre el DOCX ya generado para auditar también el ensamblado.

### 1.2 Resultado posible

| Resultado | Definición | Consecuencia |
|-----------|------------|-------------|
| **CONFORME** | Sin incoherencias materiales, sin observaciones abiertas, sin gaps de criticidad alta que comprometan la cadena técnica | Expediente listo para presentación (previa resolución de pendientes si los hay) |
| **CON OBSERVACIONES** | Sin incoherencias materiales, pero con observaciones de redacción, gaps declarados o incidencias técnicas del DOCX | Avanza en modo test; en expediente real requiere resolver las observaciones antes de presentar |
| **NO CONFORME** | Incoherencia material activa, o gap bloqueante no declarado, o dato provisional presentado como resuelto | No puede avanzar hasta corregir |

**Regla absoluta**: M-12 no puede emitir CONFORME si existe una incoherencia material activa entre los datos del expediente (datos identificativos, objeto evaluado, significancias, cadena impactos-medidas-PVA).

---

## §2. Inputs que M-12 debe revisar

M-12 revisa tres capas del expediente:

### 2.1 Contenido técnico (bloques A a K)
Todos los bloques del DA redactados por AG-10:
- `bloques/A_identificacion_y_descripcion.md`
- `bloques/B_inventario_ambiental.md`
- `bloques/C_impactos.md`
- `bloques/D_medidas.md`
- `bloques/E_PVA.md`
- `bloques/F_alternativas.md`
- `bloques/G_vulnerabilidad.md`
- `bloques/H_red_natura_2000.md`
- `bloques/I_conclusiones.md`
- `bloques/J_resumen_no_tecnico.md`
- `bloques/K_referencias.md`
- `bloques/00_triaje.md` (ficha interna de triaje)

### 2.2 Capas de datos (outputs de AG-01 a AG-09)
- `capas/hechos_confirmados.json`
- `capas/inferencias_y_gaps.json`
- `capas/normativa_aplicable.json`
- `capas/cartografia_trace.json`
- `impactos/identificacion_valoracion_impactos.json`
- `impactos/medidas_correctoras.json`
- `impactos/pva.json`
- `control_interno/ficha_objeto_evaluado.md`

### 2.3 Ensamblado documental (M-11)
- `output/DA_[expediente]_vX.docx` — estructura OOXML, modos de apertura, mapas, codificación
- `mapas/` — presencia y referencias de todos los MAP-XXX
- `clima/climograma.svg` o `.png` — presencia e inserción en el DOCX

---

## §3. Los nueve ejes de auditoría

### EJE 1 — Coherencia del objeto evaluado

Verificar que los datos estructurales del objeto evaluado son consistentes a través de todos los bloques:

| Dato | Bloques donde aparece | Verificación |
|------|-----------------------|-------------|
| RC | A, I, portada, 00_triaje, ficha_objeto_evaluado | Valor idéntico en todos |
| Superficie evaluada | A, C, I, J | Valor idéntico, siempre con nota GAP si delimitación pendiente |
| Coordenadas | A únicamente | No deben replicarse incorrectamente en otros bloques |
| Capacidades (t/día, t/año, t máx) | A, C, I, J | Valores consistentes entre bloques |
| Operaciones incluidas (R1201, R1302, etc.) | A, C, D, G, I | Mismos códigos en todos |
| Operaciones excluidas (R1203=0, etc.) | A, C, G | Excluidas en todos los bloques donde podría haberse colado |
| Promotor / NIF | A, I, J, portada | Idénticos |
| Técnico redactor | A, I, J, portada, 00_triaje | Idénticos |

Señal de alarma: una capacidad aparece con valor diferente en dos bloques; una operación excluida en A.4.3 aparece descrita implícitamente en C o G.

### EJE 2 — Coherencia inventario → impactos

Verificar que cada impacto de AG-09 tiene factor receptor en AG-08, y que el nivel de certeza del factor receptor se ha propagado como qualifier en la descripción del impacto en Bloque C:

- ¿Cada IMP-XX referencia un FR-XX que existe en el inventario?
- ¿Los factores con semáforo INFERIDO_TECNICO o inferior tienen qualifier en la descripción del impacto de Bloque C?
- ¿Los factores con `listo_para_ag09: false` tienen `significancia: INDETERMINADO` en AG-09?
- ¿Los qualifiers de AG-08 ("no se detecta en fuentes consultadas", "sin prospección de campo") están en la descripción del impacto correspondiente en Bloque C?

### EJE 3 — Coherencia impactos → medidas → PVA

Verificar la cadena completa:

| Impacto | Tiene medida | Tiene PVA | Coherencia medidas entre C y D | Coherencia PVA entre C y E |
|---------|-------------|----------|-------------------------------|---------------------------|
| IMP-XX (nuclear Moderado o superior) | Obligatoria | Obligatorio | — | — |
| IMP-XX (nuclear Compatible) | Recomendada | Recomendado | — | — |
| IMP-XX (nuclear Compatible residual) | Obligatoria (la que produce la reducción) | Básico | — | — |
| IMP-XX (condicionante transversal) | Externa al EIA | No aplica en EIA | — | — |
| IMP-XX (positivo) | No aplica | Indicador de eficacia si aplica | — | — |

Verificar que las medidas listadas en Bloque D son las mismas que las asociadas en Bloque C para cada impacto. Verificar que las fichas PVA de Bloque E referencian los mismos impactos y medidas que las fichas en `pva.json`.

### EJE 4 — Prudencia jurídica y técnica

Verificar que el expediente respeta las reglas de prudencia establecidas en los prompts de AG-10:

**Sub-eje 4a — Sin ausencias sin evidencia**:
- ¿Algún bloque afirma "no existe [flora/fauna/patrimonio]" sin prospección de campo o consulta formal?

**Sub-eje 4b — Sin valoraciones anticipadas en inventario**:
- ¿El Bloque B contiene frases de valoración de impacto ("el proyecto no afectará a...", "la actividad es compatible con...")?

**Sub-eje 4c — Sin elevación de certeza en la cadena AG-08→Bloque B→Bloque C→Bloque J**:
- Comparar el nivel de certeza declarado en las fichas AG-08 con la redacción de los bloques correspondientes. ¿Algún bloque suena más seguro que la ficha de origen?

**Sub-eje 4d — Terminología Natura 2000 correcta**:
- ¿El Bloque H usa "afección apreciable" (no "significativa")?
- ¿La conclusión H.4 tiene las tres partes obligatorias: localización + vectores + limitación?
- ¿El Bloque J mantiene el mismo nivel de prudencia que H.4 (patrón OBS-002)?

**Sub-eje 4e — Distinción promotor / órgano ambiental**:
- ¿El Bloque I declara explícitamente que sus conclusiones son las del promotor (DA)?
- ¿El DA evita formular el IIA o anticipar su contenido?
- ¿El Bloque J remite la decisión final al órgano ambiental (J.8)?

### EJE 5 — Trazabilidad

Verificar que los datos sensibles tienen trazabilidad a HC-XXX o a fuente documental:

- Datos DECLARADO: ¿la fuente está citada explícitamente?
- Datos CONFIRMADO: ¿hay al menos dos fuentes coincidentes o un instrumento independiente?
- Datos de normativa: ¿están en `normativa_aplicable.json` con referencia al BOE/BOC?
- Datos cartográficos: ¿están en `cartografia_trace.json` con referencia MAP-XXX?
- Datos climáticos: ¿están referenciados a la API AEMET o fuente alternativa documentada?

### EJE 6 — Gaps y pendientes

Verificar que todos los gaps activos de `inferencias_y_gaps.json` están declarados visiblemente en los bloques correspondientes, y no absorbidos en la redacción:

- ¿Cada GAP-XXX de criticidad alta tiene nota visible en el bloque donde afecta?
- ¿Los pendientes del expediente real aparecen en la sección de pendientes del Bloque I?
- ¿Ningún dato provisional se presenta como resuelto?

### EJE 7 — Consistencia documental del DOCX

Si el DOCX ha sido ensamblado por M-11:

- ¿El archivo se abre en Word sin error bloqueante?
- ¿La portada incluye: promotor, RC, redactor, fecha, modo de elaboración?
- ¿El orden de bloques es A→B→C→D→E→F→G→H→I→J→K?
- ¿El bloque 00 (triaje) está aislado como apéndice interno, no como parte del cuerpo del DA?
- ¿La codificación es UTF-8 (sin caracteres corruptos en vocales acentuadas y eñes)?
- ¿Las tablas tienen encabezados distinguibles del cuerpo?

### EJE 8 — Consistencia de mapas y cartografía

- ¿Todos los MAP-XXX citados en los bloques existen en `mapas/`?
- ¿Todos los MAP-XXX están insertados en el DOCX (Anejo Cartográfico)?
- ¿Cada mapa tiene caption identificando fuente, escala y fecha?
- ¿El climograma (SVG o PNG) está insertado o documentada su ausencia?
- ¿Los servicios WMS DESCARTADOS (si los hay) están documentados en `servicios_WMS_verificados.json`?

### EJE 9 — Consistencia del RNT respecto al análisis técnico

El RNT (Bloque J) es la síntesis no técnica del DA y debe ser estrictamente subordinado al contenido técnico:

| Verificación | Foco |
|-------------|------|
| Distancias ENP/Natura en J iguales o más conservadoras que B/H | No puede ser más categórico |
| Significancias en J.5 iguales a las de C.4 | Sin diferencias de nivel |
| Impactos positivos de J.4 con factor receptor concreto | Sin frases genéricas |
| Conclusión J.8 con la remisión al órgano ambiental | No puede presentar el DA como resolución |
| J.7 sobre Natura 2000: mantiene "no se aprecia afección apreciable" + limitaciones | Patrón anti-OBS-002 |
| Modo de elaboración declarado en J.1 coherente con el declarado en B | Modo gabinete visible en el RNT |

---

## §4. Tipos de hallazgo

| Tipo | Definición | Consecuencia sobre el resultado |
|------|------------|--------------------------------|
| **INCOHERENCIA MATERIAL** | Contradicción entre datos estructurales de dos o más bloques (RC distinta, superficie diferente, significancia que varía entre C y I, operación excluida que aparece incluida en otro bloque) | → NO CONFORME hasta resolución |
| **OBSERVACIÓN** | Imprecisión de redacción, qualifier perdido, tono más categórico de lo que la evidencia permite, gap declarado pero sin nota visible en el bloque afectado | → CON OBSERVACIONES; en expediente real requiere corrección antes de presentar |
| **INCIDENCIA TÉCNICA** | Problema de ensamblado DOCX (referencia rota, encoding, rutas ZIP) sin impacto en el contenido del DA | → CON OBSERVACIONES; corrección antes del expediente real |
| **PENDIENTE** | Gap o cautela abierta que está correctamente declarada en el expediente y que no altera la coherencia técnica, pero debe resolverse antes de la presentación formal | → CON OBSERVACIONES (en modo test no bloquea) |
| **FORTALEZA** | Elemento del expediente que funciona especialmente bien y debe documentarse como referencia positiva | → Registro en la sección de fortalezas del informe |

### Diferencia entre error material y observación

- **Material**: la contradicción afecta a datos que dos o más bloques del DA declaran de forma diferente, o a un dato que el expediente usa como premisa de un análisis y que es incorrecto. Ejemplos: superficie evaluada con valor distinto en A y en C; significancia de IMP-01 declarada Moderado en C.4 y Compatible en I.3.2; operación R1203 excluida en A.4.3 pero descrita implícitamente como disponible en G.
- **Observación**: la información técnica es coherente entre bloques pero la redacción es más categórica de lo que la evidencia permite, o un qualifier se perdió en la transición entre bloques. No hay contradicción factual, hay pérdida de matiz. Ejemplo: H.4 dice "no se prevé afección apreciable según análisis gabinete" y J.7 dice "el proyecto no afecta a Natura 2000" — los datos son consistentes, pero J.7 ha perdido el qualifier.

---

## §5. Cómo distinguir modo test vs expediente real en el informe de auditoría

El informe M-12 siempre declara explícitamente el modo de elaboración del expediente auditado y sus consecuencias:

**En modo TEST**:
- Los gaps de criticidad alta que están correctamente declarados no producen NO CONFORME, pero se listan como pendientes para expediente real.
- Las incidencias técnicas del DOCX no producen NO CONFORME si no afectan al contenido.
- El resultado CON OBSERVACIONES en modo test equivale a "técnicamente sólido para avanzar; pendientes identificados para cuando se prepare la presentación formal".

**En expediente REAL**:
- Cualquier gap de criticidad alta no resuelto que afecte a datos del DA es una incoherencia potencial respecto a lo que el órgano ambiental encontrará.
- Las observaciones de redacción (especialmente OBS-002 y similares de tono Natura 2000) deben resolverse antes de presentar.
- El DOCX debe abrirse sin avisos de reparación en Word.

El informe M-12 incluye una sección explícita: "Para que este expediente sea presentable en expediente real, deben resolverse: [lista ordenada por criticidad]".

---

## §6. Estructura mínima del informe de auditoría

```markdown
# INFORME DE AUDITORÍA FINAL — M-12
## [Nombre del expediente]

**Fecha de auditoría**: [fecha]
**Modo**: TEST / PRODUCCIÓN — [descripción]
**Alcance**: art. 45 Ley 21/2013 + coherencia interna + trazabilidad + ensamblaje DOCX

> **Nota de alcance**: [nota distinguiendo M-12 del IIA del órgano ambiental]

## 1. Documentos auditados
[Tabla de bloques + capas + DOCX con estado "Auditado / Revisado / No disponible"]

## 2. Checklist art. 45 + Anexo VI Ley 21/2013
[Tabla: requisito / artículo / bloque / resultado (CONFORME / CONFORME CON OBSERVACIÓN / NO CONFORME)]

## 3. Coherencia interna — resultados por eje
### 3.1. EJE 1 — Datos identificativos y objeto evaluado
### 3.2. EJE 2 — Inventario → impactos (qualifiers heredados)
### 3.3. EJE 3 — Impactos → medidas → PVA (cadena completa)
### 3.4. EJE 4 — Prudencia jurídica y técnica
### 3.5. EJE 5 — Trazabilidad
### 3.6. EJE 6 — Gaps y pendientes visibles
### 3.7. EJE 7 — DOCX (si disponible)
### 3.8. EJE 8 — Cartografía
### 3.9. EJE 9 — RNT vs análisis técnico (anti-OBS-002)

## 4. Fortalezas del expediente
[Elementos que funcionan bien — referencia para futuros expedientes]

## 5. Observaciones y no conformidades
### 5.X. [Código] — [Denominación] ([Severidad])
[Descripción / valoración / acción recomendada para expediente real]

## 6. Pendientes para expediente real
[Tabla ordenada por criticidad: ID / descripción / criticidad]

## 7. Valoración del DOCX ensamblado
[Tabla de aspectos técnicos del DOCX]

## 8. Verificación distinción promotor / órgano ambiental
[Tabla de puntos de verificación]

## 9. Resumen ejecutivo
[Fortalezas principales / incoherencias detectadas / pendientes relevantes / situación DOCX]

## 10. Conclusión final
[Una o dos frases + calificación: CONFORME / CON OBSERVACIONES / NO CONFORME + fundamento]
```

---

## §7. Relación con art. 45, Anexo VI y ensamblado documental

### 7.1 Checklist art. 45

El art. 45 de la Ley 21/2013 establece el contenido mínimo del Documento Ambiental para EIA simplificada. El Anexo VI precisa el contenido del documento. M-12 verifica sistemáticamente que todos los requisitos del Anexo VI están presentes en el expediente:

| Requisito Anexo VI | Bloque(s) | Verificación |
|-------------------|-----------|-------------|
| §1 — Localización geográfica y descripción del proyecto | A | Presencia y completitud |
| §2 — Descripción del estado del lugar | B | Presencia; modo de elaboración declarado |
| §3 — Examen de alternativas razonables | F | Presencia; no requiere campo para EIA simplificada |
| §4 — Efectos notables previsibles | C | Impactos identificados con metodología |
| §5 — Medidas para prevenir y corregir efectos | D | Medidas para todos los impactos Moderado o superior |
| §6 — Programa de Vigilancia Ambiental | E | PVA con indicadores y umbrales |
| §7 — Vulnerabilidad del proyecto | G | Presencia; riesgos naturales analizados |
| §8 — Resumen no técnico | J | Presencia; coherencia con el análisis técnico |
| Art. 46 — Afección a Natura 2000 | H | Análisis de vectores; terminología correcta |
| Art. 16 — Capacidad técnica del redactor | A.2 | Titulación y colegiación acreditadas |

### 7.2 Relación con el ensamblado M-11

M-12 es la validación del output de M-11 (si ya se ha ensamblado). Pero M-12 puede ejecutarse sobre los bloques markdown aunque el DOCX no esté todavía ensamblado. En ese caso, el Eje 7 (DOCX) se ejecuta en modo "pendiente de ensamblado" y se reporta como tal.

La secuencia recomendada: AG-10 (redacción bloques) → M-12 (auditoría de contenido) → corrección de observaciones materiales → M-11 (ensamblado DOCX) → M-12 (auditoría del DOCX).

---

## §8. Lecciones del piloto Recimetal

### L-01: Lo que funcionó bien y se codifica como obligatorio

**Las nueve secciones del informe**: estructura completa de documentos auditados → checklist art. 45 → coherencia por eje → fortalezas → observaciones → pendientes → DOCX → promotor/órgano → resumen → conclusión. Esta estructura es reproducible sin importar el expediente.

**Tabla de coherencia de significancias entre C, D e I**: en el piloto esta tabla detectó que los valores eran consistentes. En expedientes futuros puede detectar la inconsistencia si existe. Es la verificación más directa de que el expediente no tiene contradicciones materiales de valoración.

**Distinción severidad baja vs media vs bloqueante**: el piloto distinguió OBS-001 (baja, sin PVA para dos impactos compatibles) de OBS-002 (baja-media, tono más categórico en J.7) de los pendientes de criticidad alta (gaps reales). Esta graduación evita que el informe de auditoría suene igual para un problema cosmético que para un gap que puede paralizar la resolución.

**Tabla de pendientes para expediente real ordenada por criticidad**: en el piloto esta tabla tiene 15 entradas con criticidad explícita. El órgano ambiental y el promotor pueden leer directamente lo que falta antes de presentar.

**Registro de fortalezas**: sección explícita con 10 fortalezas del expediente. Esto documenta lo que funciona bien para que los expedientes futuros puedan replicarlo.

### L-02: Huecos del checklist del piloto que se corrigen en v2.1

**Sub-eje 4c (elevación de certeza en la cadena)**: el piloto detectó OBS-002 (J.7 más categórico que H.4) pero no sistematizó la verificación de toda la cadena AG-08→Bloque B→Bloque C→Bloque J. En v2.1 el Eje 2 hace esta verificación explícita para todos los factores con semáforo INFERIDO_TECNICO o inferior.

**Sub-eje 4d (terminología "apreciable")**: el piloto detectó que J.7 usó "no afecta" en lugar de "no se aprecia afección apreciable". En v2.1 el Eje 9 tiene verificación explícita de la terminología "apreciable" en H y en J.

**Eje de qualifiers de las medidas**: el piloto verificó la cadena C→D→E pero no verificó específicamente si las medidas suenan más eficaces en Bloque D que en `medidas_correctoras.json`. En v2.1 el Eje 3 incluye esta verificación.

### L-03: La calificación CON OBSERVACIONES como patrón para modo test

El piloto Recimetal cerró con "EXPEDIENTE CON OBSERVACIONES EN MODO TEST". Este es el patrón normal para un expediente en modo gabinete puro sin campo: la cadena técnica es correcta y coherente, pero hay gaps reales de campo (flora, fauna, patrimonio) que no pueden resolverse en gabinete. La calificación CON OBSERVACIONES no es un fracaso — es el diagnóstico correcto para un expediente que está listo para avanzar con sus limitaciones declaradas.

Lo que sería anomalía: un expediente en modo gabinete puro que cierra como CONFORME. Eso significaría que M-12 no está detectando los gaps reales o que los está tratando como resueltos cuando no lo están.
