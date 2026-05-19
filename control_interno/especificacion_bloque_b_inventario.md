# Especificación técnica — AG-10 / Bloque B: Inventario ambiental
**Versión**: 2.1  
**Estado**: VALIDADO  
**Fecha**: 2026-04-15  
**Baseline**: piloto-recimetal + criterios P2

---

## §1. Qué es un Bloque B válido en este sistema

El Bloque B es la **traducción narrativa del inventario probatorio** de AG-08 al lenguaje del Documento Ambiental. No es una descripción del territorio; es una descripción del territorio **con sus limitaciones epistémicas visibles**.

Un Bloque B es válido si y solo si cumple estas condiciones:

1. **Trazabilidad total**: cada dato citable lleva referencia a ficha AG-08 (FI-XX) y a fuente cartográfica o documental (MAP-XXX, DOC-XXX).
2. **Paridad de certeza**: el nivel de certeza declarado en Bloque B no supera el nivel del semáforo de AG-08 para ese factor.
3. **Limitaciones visibles**: las limitaciones de gabinete, las ausencias de datos y los gaps abiertos no se disuelven en la prosa; se declaran explícitamente.
4. **Advertencias obligatorias**: flora, fauna, y patrimonio tienen siempre un párrafo de advertencia con texto estandarizado, independientemente de cuánto (o poco) se haya encontrado en gabinete.
5. **Cobertura completa**: los 16 factores del inventario AG-08 aparecen en el bloque, aunque su evidencia sea débil. Un factor NO_CONSTA no se omite — se declara como pendiente.
6. **Modo declarado**: el encabezamiento del bloque declara explícitamente si el inventario fue elaborado en modo gabinete, con qué instrumentos, y qué limitaciones generales se derivan de ello.

Lo que el Bloque B **no es**:
- No es un resumen de la parte medioambiental de internet
- No es una descripción del territorio tipo "informe de situación"
- No es el lugar para rellenar vacíos de datos con prosa plausible
- No es el lugar para emitir conclusiones sobre ausencias no probadas

---

## §2. Relación exacta entre AG-08 y Bloque B

El Bloque B es un output subordinado a AG-08. La relación es unidireccional y sin retorno:

```
AG-08 (fichas probatorias) → AG-10/bloque_B (traducción narrativa)
```

AG-10 no puede:
- Modificar el semáforo de evidencia de AG-08
- Usar datos que no estén en las fichas AG-08 o en las capas JSON
- Declarar un factor como más cerrado de lo que AG-08 lo dejó
- Omitir un gap que AG-08 registró

AG-10 puede y debe:
- Redactar con fluidez y rigor técnico los contenidos de las fichas
- Hacer la síntesis narrativa de tablas y valores
- Añadir contexto descriptivo del entorno cuando tenga fuente citada
- Indicar, de forma clara al lector técnico, qué se sabe, cómo se sabe y qué no se sabe

### Correspondencia de campos

| Campo AG-08 | Uso en Bloque B |
|-------------|-----------------|
| `denominacion` | Título del subapartado |
| `semaforo_evidencia` | Etiqueta de certeza en el encabezado del apartado |
| `dato_principal` | Contenido narrativo del apartado |
| `fuentes_usadas` | Referencias MAP-XXX / DOC-XXX / FI-XX al pie o en línea |
| `limitaciones` | Párrafo de limitaciones o `> Advertencia` |
| `gaps_criticos` | Referencia explícita al GAP-XXX y acción requerida |
| `listo_para_ag09` | No aparece en texto, pero si es false debe haber advertencia visible |
| `afirmaciones_cualificadas` | Deben reproducirse literalmente en la prosa |
| `semaforo_campo` | Determina si se añade recomendación de campo |

---

## §3. Herencia del estado de evidencia — tabla de traducción

La correspondencia entre el semáforo AG-08 y la forma de redactar en Bloque B es la siguiente:

| Estado AG-08 | Certeza en título | Formulación permitida | Formulación prohibida |
|--------------|-------------------|-----------------------|-----------------------|
| CONFIRMADO_CAMPO | ALTA | "Se constata mediante prospección de campo que..." / "La prospección botánica confirma..." | "Según fuentes consultadas..." (bajar la certeza cuando hay campo) |
| CONFIRMADO_GABINETE | ALTA (gabinete) | "La cartografía consultada confirma..." / "Según [fuente concreta] (MAP-XXX)..." | "Se confirma sin lugar a dudas que..." (no elevar a CAMPO) |
| INFERIDO_TECNICO | MEDIA | "Se estima/infiere técnicamente que..." / "El contexto territorial sugiere..." / "A partir de [dato], se deduce que..." | "Se confirma que..." / "No existe..." |
| LIMITADO_ESCALA | BAJA | "La escala cartográfica disponible (1:XXX) no permite caracterizar con detalle..." / "Los datos consultados son insuficientes para..." | "Según los datos disponibles, no hay..." |
| PENDIENTE_VERIFICACION | MUY BAJA / PENDIENTE | "No se dispone de datos suficientes para caracterizar este factor. Consulta pendiente (GAP-XX)." | Cualquier afirmación sustantiva sobre el factor |
| NO_CONSTA | MUY BAJA / NO CONSTA | "No se han podido obtener datos sobre este factor en la fase de gabinete. Ver GAP-XX." | Cualquier afirmación sustantiva sobre el factor |

**Regla de herencia estricta**: si la ficha AG-08 tiene `semaforo_evidencia: LIMITADO_ESCALA`, el texto del Bloque B no puede contener ninguna oración afirmativa sobre ese factor sin qualifier explícito. El qualifier no puede estar solo en la primera oración si el párrafo continúa con afirmaciones sin qualifier.

---

## §4. Tratamiento por factor — instrucciones específicas

### Flora y vegetación (FI-07)

**Regla absoluta**: No existe la posibilidad de afirmar ausencia de flora protegida a partir de ortofoto. La ortofoto muestra cobertura visual, no determinación botánica. Siempre incluir la advertencia:

> **Advertencia**: La ausencia de flora protegida en la parcela y su entorno **no puede afirmarse sin prospección botánica de campo**. La vegetación potencial [del ámbito geográfico] incluye [taxones relevantes del ámbito geográfico]. En el expediente real, si existen zonas con suelo desnudo o márgenes no pavimentados, se requiere prospección botánica y consulta del [atlas/catálogo de flora correspondiente] (GAP-INV-XXX).

Lo que sí puede decirse a partir de ortofoto: descripción de la cobertura visual ("sin cubierta vegetal aparente en la ortofoto"), con referencia explícita a que es una observación de ortofoto, no una determinación botánica.

Nivel semáforo mínimo aceptable para no bloquear AG-09: INFERIDO_TECNICO si el contexto es claramente industrializado. LIMITADO_ESCALA si hay zonas de suelo natural en el entorno.

### Fauna (FI-08)

**Regla absoluta**: No existe la posibilidad de afirmar ausencia de fauna protegida a partir de ortofoto ni de contexto territorial. El contexto industrial reduce la probabilidad, pero no la elimina. Siempre incluir la advertencia:

> **Advertencia**: La presencia o ausencia de fauna protegida **no puede determinarse sin prospección de campo y consulta al [banco de datos de biodiversidad correspondiente]**. En el expediente real, la prospección de fauna es requerida antes del cierre del inventario (GAP-INV-XXX).

Lo que sí puede decirse: fauna sinantrópica inferida a partir del contexto (con qualifier "se infiere", no "se confirma"), y riesgos asociados documentados (ej: roedores en acopios de chatarra).

Nivel semáforo mínimo aceptable para no bloquear AG-09: INFERIDO_TECNICO para fauna sinantrópica. Fauna protegida: siempre PENDIENTE_VERIFICACION si no hay campo.

### Patrimonio cultural (FI-12)

**Regla absoluta**: No puede afirmarse ni descartarse la presencia de elementos patrimoniales sin consulta formal a los servicios de patrimonio competentes. Siempre incluir la advertencia:

> **Advertencia**: No puede afirmarse ni descartarse la presencia de yacimientos arqueológicos, bienes de interés cultural o elementos etnográficos sin consulta al [servicio de patrimonio competente] y al [sistema de información del patrimonio correspondiente]. En el expediente real, esta consulta es **obligatoria** antes del cierre del inventario (GAP-INV-XXX).

El hecho de que el proyecto no incluya excavaciones es un dato del objeto evaluado (AG-04) que reduce el riesgo directo, pero no elimina la obligación de consulta para el patrimonio del entorno. Puede mencionarse, pero como contextualización, nunca como sustituto de la consulta.

Nivel semáforo mínimo aceptable para no bloquear: PENDIENTE_VERIFICACION siempre en modo gabinete puro. Solo CONFIRMADO_GABINETE si hay respuesta documental del organismo competente.

### Ruido y receptores acústicos (FI-14)

Sin mediciones acústicas de fondo (Leq de la zona), no puede afirmarse que el impacto acústico será "sin efecto perceptible" o "inapreciable". Lo que sí puede argumentarse:
- El contexto industrial implica ruido de fondo preexistente elevado (INFERIDO a partir del tipo de zona)
- La exclusión de determinadas operaciones (si AG-04 lo confirma) elimina fuentes de mayor intensidad
- La medida organizativa de restricción horaria es la respuesta proporcional al nivel de certeza

No puede escribirse: "No se prevén impactos acústicos significativos" sin medición o sin referencia a receptores acústicos sensibles identificados y su distancia.

### Hidrología y drenaje (FI-04)

Si el anejo de drenaje no ha sido aportado (gap abierto), no puede caracterizarse el sistema de drenaje como "adecuado" o "suficiente". Solo puede describirse lo declarado por el promotor, con referencia al gap que impide la verificación.

Sobre cursos de agua: "no se detectan cursos permanentes en las fuentes consultadas" es la formulación correcta. "No existen cursos de agua en el entorno" no lo es.

### ENP y Natura 2000 (FI-09, FI-10)

Formulación estándar para ausencia de superposición directa:

> "La cartografía consultada (MAP-XXX) no muestra superposición directa entre la zona de actuación y ningún [espacio ENP / espacio Natura 2000] de [ámbito geográfico]. La distancia estimada al [espacio] más próximo es de [X] km según lectura visual de la cartografía WMS consultada, valor que debe verificarse con análisis GIS sobre las geometrías oficiales del [organismo competente] en el expediente real."

Las tres cosas que no pueden omitirse:
1. La fuente cartográfica exacta (MAP-XXX)
2. El qualifier "estimada" sobre la distancia si no es análisis GIS
3. La remisión al Bloque H para el análisis de afección indirecta

Si la parcela está a más de 10 km de cualquier espacio protegido y en zona industrial consolidada, el análisis puede ser más breve, pero los tres elementos siguen siendo obligatorios.

---

## §5. Afirmaciones prohibidas

Las siguientes formulaciones están prohibidas en el Bloque B independientemente del contexto:

| Formulación prohibida | Por qué | Alternativa correcta |
|-----------------------|---------|----------------------|
| "No existe [elemento ambiental] en el área" | Afirma ausencia sin evidencia negativa | "No se detecta [elemento] en las fuentes consultadas" |
| "El proyecto no afectará a [factor]" | Es valoración de impacto, no inventario | Reservar para Bloque C |
| "Dado el contexto industrial, se descarta la presencia de fauna protegida" | El contexto reduce probabilidad, no la elimina | "El contexto industrial reduce la probabilidad de presencia de fauna protegida, aunque no puede descartarse sin prospección de campo" |
| "La ausencia de vegetación confirma que no hay flora protegida" | Ortofoto ≠ determinación botánica | "La ortofoto no muestra cubierta vegetal aparente; la ausencia de flora protegida no puede confirmarse sin prospección" |
| "Compatible con el entorno" | Es valoración de compatibilidad, no inventario | Reservar para Bloque C o Bloque D |
| "No procede análisis de [factor]" | Todo factor del inventario AG-08 aparece en el bloque | "No se dispone de datos sobre [factor]. Ver GAP-XX." |
| "Sin relevancia para el expediente" sobre un factor con semáforo NO_CONSTA | Puede ser relevante; no se sabe | "No se han podido obtener datos sobre este factor. GAP-XX abierto." |
| "Según la legislación vigente, no se requiere..." sobre patrimonio o fauna | La legislación no sustituye la evidencia | Hacer la consulta requerida; si no es posible en gabinete, declarar el gap |
| Distancias a ENP/Natura sin qualifier "estimada" | Las distancias visuales no son análisis GIS | Añadir qualifier; remitir a análisis GIS en expediente real |
| "[Elemento] confirmado" sin especificar el modo (gabinete / campo) | "Confirmado" sin modo es ambiguo | "[Elemento] confirmado en modo gabinete (fuente: MAP-XXX)" |

---

## §6. Documentación de limitaciones y necesidades de campo

### 6.1 Advertencia general de modo

El Bloque B debe abrir con una advertencia general que declare:
- Modo de elaboración (gabinete / mixto / campo completo)
- Instrumentos utilizados (cartografía WMS, API AEMET, documentos del promotor)
- Limitación general: la ausencia de un elemento en las fuentes consultadas no equivale a su inexistencia en el terreno

Este párrafo es **obligatorio** en modo gabinete o mixto. No es opcional aunque el proyecto sea pequeño.

### 6.2 Advertencias específicas obligatorias

Los factores con `semaforo_campo: CAMPO_NECESARIO` en `semaforo_campo.md` (AG-08) **siempre** tienen un párrafo de advertencia visible en el Bloque B, con referencia al GAP correspondiente y a la acción requerida en el expediente real.

Los factores con `semaforo_campo: CAMPO_RECOMENDADO` tienen al menos una frase de limitación, aunque no necesariamente en bloque de advertencia.

### 6.3 Formato de la advertencia

Usar blockquote para las advertencias formales:

```
> **Advertencia**: [texto de advertencia con referencia al gap]
```

No enterrar la advertencia en mitad de un párrafo narrativo. La advertencia debe ser visible al lector técnico que busca las limitaciones del inventario.

### 6.4 Referencias a GAPs

Los gaps se referencian en el punto donde son relevantes, con su código exacto:
- `GAP-XXX` para gaps del expediente general
- `GAP-INV-XXX` para gaps del inventario específico

No basta con mencionar el gap en la tabla final. Debe estar en el texto del apartado correspondiente.

---

## §7. Estructura mínima del Bloque B

```markdown
# BLOQUE B — Inventario ambiental
## [Nombre del expediente]

**Modo**: [GABINETE / MIXTO / CAMPO]  
[Advertencia general de modo obligatoria]

## B.1. Descripción del entorno
[Síntesis del contexto territorial con referencias MAP-XXX]

## B.2. [FI-01: Clima] — Certeza [ALTA/MEDIA/BAJA/MUY BAJA]
**Fuente**: [fuente concreta]
[Contenido narrativo]

## B.3. [FI-02: Geología] — Certeza [...]
...

[Un apartado por cada uno de los 16 factores FI-01 a FI-16]
...

## B.17. [FI-16: Riesgos naturales — síntesis] — Certeza [...]
[Síntesis de riesgos con referencias a Bloque G]

## B.18. Tabla resumen del inventario
| Factor | Certeza | Resultado principal | Relevancia para impactos |
[Tabla con los 16 factores]
```

La numeración B.2 a B.17 corresponde a FI-01 a FI-16. B.1 es el contexto territorial (no es una ficha AG-08 individual). B.18 es la tabla de síntesis.

**Factores con evidencia débil (PENDIENTE_VERIFICACION / NO_CONSTA)**: no se omiten. El apartado existe con el texto de advertencia y la referencia al gap. Un bloque vacío es preferible a un apartado ausente.

---

## §8. Modo test vs expediente real

| Aspecto | Modo TEST | Expediente REAL |
|---------|-----------|-----------------|
| Campos PENDIENTE_VERIFICACION | Permitidos — declarar con advertencia | Idealmente resueltos antes de presentación |
| Campos NO_CONSTA | Permitidos — declarar con GAP | Deben resolverse con consulta o prospección |
| Flora y fauna sin campo | Permitido en test con advertencia | Requiere prospección o justificación de no necesidad |
| Patrimonio sin consulta | Permitido en test con advertencia | Consulta obligatoria a organismo competente |
| Distancias ENP/Natura estimadas | Permitido con qualifier | Verificar con geometrías oficiales |
| Tabla de certeza con niveles BAJOS | Aceptable | Aceptable con justificación |

En modo TEST, el gate 7 (redacción) acepta un Bloque B con hasta 4 factores en estado PENDIENTE_VERIFICACION / NO_CONSTA, siempre que:
- Estén declarados como tales con advertencia explícita
- Los gaps correspondientes estén en `inferencias_y_gaps.json`
- Ninguno de ellos sea FI-09 (ENP) o FI-10 (Natura 2000) en zonas con ENP próximos

---

## §9. Lecciones del piloto Recimetal

### L-01: Lo que funcionó bien

- **Advertencia general al inicio**: el párrafo de modo gabinete al comienzo del bloque es exactamente el patrón correcto. Debe mantenerse en todos los expedientes.
- **Advertencias específicas en flora, fauna y patrimonio**: en blockquote, visibles, con referencia al gap y a la acción requerida. Patrón a mantener y codificar como obligatorio.
- **Certeza en el título de cada apartado**: "FI-07 — Certeza BAJA" comunica al lector técnico la calidad del dato antes de leer el contenido. Patrón a mantener.
- **Tabla de síntesis B.18**: mapea certeza con relevancia para impactos. Es el puente explícito entre el inventario y el bloque de impactos. Obligatoria.
- **Referencias GAP en el texto**: los gaps no solo aparecen en la tabla final; se referencian en el párrafo donde son relevantes. Patrón correcto.
- **Distinción ENP/Natura**: dos apartados separados con formulación cuidadosa, distancias con qualifier "estimada", remisión al Bloque H. Correcto.

### L-02: Factores que quedaron más débiles

**FI-02 Geología (B.3)**: La frase "No se prevén impactos sobre la geología o el sustrato dado que la actividad no incluye excavaciones" es una proto-valoración de impacto dentro del bloque de inventario. El inventario no valora impactos; los describe. La formulación correcta es: "La actividad no incluye excavaciones ni movimientos de tierra según el objeto evaluado (AG-04), lo que limita las acciones causantes de impacto sobre el sustrato." La valoración formal va en Bloque C.

**FI-09 ENP (B.10)**: El estado "[Estado: CONFIRMADO (modo gabinete, cartografía consultada) — el proyecto no se superpone con ningún ENP catalogado según MAP-005; la distancia no ha sido cuantificada con geometrías exactas en modo gabinete]" es correcto en contenido pero queda al final del párrafo como etiqueta. En v2.1 la certeza debe ir en el **título del apartado** y la limitación en un párrafo o frase separada, no en una etiqueta entre corchetes al final. Más legible, más trazable.

**FI-14 Ruido (B.15)**: La sección dice "Sin mediciones de ruido de fondo" pero luego hace inferencias sobre el nivel de ruido del contexto sin qualifier explícito. El patrón debe ser: primero declarar la limitación, luego la inferencia, con el qualifier en cada oración inferida.

**FI-16 Riesgos naturales (B.17)**: Al ser una síntesis de AG-07, no tiene referencias individuales a las fichas de riesgo. En v2.1 debe referenciar explícitamente los ficheros de AG-07 o las secciones del inventario de clima.

### L-03: Frases o estilos prohibidos identificados en el piloto

1. **"No se prevén impactos sobre [factor]"** dentro del Bloque B → reservar para Bloque C
2. **"Compatible con el contexto"** en el bloque de inventario → reservar para Bloque C o D
3. **"El análisis en modo gabinete confirma..."** para un factor con certeza BAJA o MUY BAJA → el modo gabinete no "confirma" factores con certeza baja; los "estima" o "indica provisionalmente"
4. **Distancias a ENP sin qualifier**: "supera los 12 km" → correctamente, "se estima superior a 12 km según lectura visual de la cartografía WMS; valor a verificar con análisis GIS"
5. **"Dado el contexto industrial..."** como argumento suficiente para concluir ausencia de cualquier elemento ambiental

### L-04: Qué debe blindarse para evitar que el redactor suene más concluyente que las fichas

La presión narrativa del redactor es hacia la conclusión. Un texto con demasiados "no se puede afirmar" suena débil. El redactor tiene incentivos para "completar" los huecos con prosa plausible. Los blindajes son:

1. **Qualifier obligatorio en cada oración sobre factor INFERIDO_TECNICO o inferior**: el qualifier no puede estar solo en la primera oración si el párrafo continúa con afirmaciones.
2. **Autochequeo explícito**: antes de cerrar cada apartado, el agente debe preguntarse: "¿Este texto suena más seguro de lo que la ficha AG-08 me permite?"
3. **Prohibición de "confirma" sin modo**: nunca "confirma" sin especificar "en modo gabinete" o "mediante prospección de campo".
4. **Advertencias en blockquote, no en prosa**: las advertencias enterradas en medio de un párrafo son fáciles de perder; los blockquotes son imposibles de ignorar.
