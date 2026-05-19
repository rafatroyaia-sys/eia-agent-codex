# Especificación técnica — AG-10 / Bloque C: Identificación y valoración de impactos
**Versión**: 2.1  
**Estado**: VALIDADO  
**Fecha**: 2026-04-16  
**Baseline**: piloto-recimetal + criterios P2

---

## §1. Qué es un Bloque C válido en este sistema

El Bloque C es la **traducción narrativa de la matriz de impactos de AG-09** al Documento Ambiental. No es un análisis propio del redactor. No añade impactos, no elimina impactos y no cambia ninguna significancia. Traslada los resultados de AG-09 con rigor técnico y los hace comprensibles para el órgano ambiental.

Un Bloque C es válido si y solo si:

1. **No altera ninguna significancia**: los valores de significancia sin medidas y con medidas del Bloque C son exactamente los de `impactos/identificacion_valoracion_impactos.json`.
2. **Los qualifiers de AG-08/AG-09 sobreviven al paso a narrativa**: si AG-09 valoró un impacto con qualifier ("según el análisis en modo gabinete", "pendiente de prospección de campo"), ese qualifier aparece en la descripción del impacto.
3. **Los impactos INDETERMINADO son visibles**: si AG-09 produjo impactos con `significancia: INDETERMINADO`, el Bloque C los muestra como tales con referencia al gap bloqueante.
4. **Los condicionantes transversales se mantienen diferenciados**: IMP-08 y similares tienen su propio apartado, identificado explícitamente como condicionante transversal fuera de la escala EIA. No se convierten en impactos nucleares ni desaparecen.
5. **Los impactos positivos tienen factor receptor concreto**: la descripción de cada impacto positivo referencia el factor receptor específico de AG-09, no una frase genérica de beneficio ambiental.
6. **Las medidas se mencionan como procedentes de AG-09**: el Bloque C no propone medidas nuevas. Si una medida aparece en el bloque, debe estar en `impactos/medidas_correctoras.json`.
7. **La tabla resumen C.4 es fiel**: muestra siempre dos columnas de significancia (sin medidas / con medidas) para impactos negativos.
8. **El párrafo de conclusión no supera lo que la tabla muestra**: ninguna frase conclusiva del Bloque C añade interpretación que no esté respaldada por los valores de la tabla.

Lo que el Bloque C **no es**:
- No es el lugar para añadir argumentos de defensa del proyecto
- No es el lugar para relativizar impactos ("aunque es Moderado, es mucho menor que en instalaciones similares")
- No es el lugar para proponer medidas adicionales a las de AG-09
- No es el lugar para resolver los impactos INDETERMINADO con valoraciones provisionales
- No es el lugar para resumir el inventario ambiental (eso es el Bloque B)

---

## §2. Relación exacta entre AG-09 y Bloque C

El Bloque C es subordinado a AG-09. La relación es unidireccional:

```
AG-09 (matriz de impactos + medidas + PVA) → AG-10/bloque_C (narrativa del análisis)
```

Los documentos fuente que el redactor debe leer antes de redactar:

| Archivo AG-09 | Secciones que alimentan el Bloque C |
|---------------|-------------------------------------|
| `identificacion_valoracion_impactos.json` | Acciones (§C.2), todos los IMP (§C.3), tabla resumen (§C.4) |
| `medidas_correctoras.json` | Referencias M-XX en cada sección IMP |
| `pva.json` | Referencias PVA-XX en cada sección IMP |
| `capas/inferencias_y_gaps.json` | Gaps que afectan a valoraciones (qualifier obligatorio) |

AG-10 no accede a las fichas AG-08 directamente para el Bloque C — accede a los outputs de AG-09, que ya incorporan la herencia del semáforo AG-08. Si la valoración de AG-09 tiene qualifier derivado de AG-08, ese qualifier está en el JSON de AG-09 y debe reproducirse.

### Correspondencia de campos

| Campo AG-09 (`identificacion_valoracion_impactos.json`) | Sección Bloque C |
|---------------------------------------------------------|-----------------|
| `acciones_proyecto` | C.2 — tabla de acciones |
| `factores_receptores` | Citados en cabecera de cada IMP |
| `valoracion_impactos[].denominacion` | Título de cada apartado C.3.X |
| `valoracion_impactos[].descripcion` | Párrafo descriptivo del impacto |
| `valoracion_impactos[].parametros_conesa` | Tabla Conesa del apartado |
| `valoracion_impactos[].significancia_sin_medidas` | Fila resumen tabla Conesa + tabla C.4 |
| `valoracion_impactos[].significancia_residual` | Fila resumen tabla Conesa + tabla C.4 |
| `valoracion_impactos[].medidas_asociadas` | Lista M-XX al pie del apartado |
| `valoracion_impactos[].pva_asociado` | Lista PVA-XX al pie del apartado |
| `valoracion_impactos[].tipo` | Determina la estructura narrativa del apartado |
| `valoracion_impactos[].qualifiers_heredados` | Reproducidos literalmente en la descripción |

---

## §3. Herencia del estado de evidencia y los qualifiers

El paso de AG-09 a Bloque C es el último punto donde un qualifier puede perderse antes de llegar al documento final. El mecanismo de pérdida es la presión narrativa: el redactor suaviza el qualifier porque "suena repetitivo" o porque "hace el texto más fluido". Esa presión debe resistirse activamente.

### 3.1 Regla de reproducción de qualifiers

Si AG-09 incorporó un qualifier en la descripción de un impacto (derivado del semáforo AG-08 del factor receptor), ese qualifier debe aparecer en la descripción del impacto en el Bloque C. No tiene que ser la misma frase literal, pero la información epistémica no puede perderse.

**Qualifier obligatorio según origen**:

| Origen del qualifier | Qualifier que debe sobrevivir en Bloque C |
|---------------------|------------------------------------------|
| Factor AG-08 con semáforo INFERIDO_TECNICO | "a partir del análisis en modo gabinete" / "según las fuentes consultadas" |
| Factor AG-08 con semáforo LIMITADO_ESCALA | "con la limitación de la escala cartográfica disponible" |
| Factor AG-08 sin prospección de campo para flora/fauna | "dado que no se ha realizado prospección de campo" |
| Gap abierto que afecta a la valoración | Referencia al código GAP-XXX en la descripción del impacto |
| CONT-XXX resuelta provisionalmente | "pendiente de confirmación formal" o referencia al estado provisional |

### 3.2 El qualifier no puede estar solo en la primera oración

Si el qualifier aplica a todo el párrafo descriptivo del impacto, debe ser visible en la posición donde el lector lo necesita (antes de la tabla Conesa o como nota al final del apartado), no solo en la primera oración cuando las oraciones siguientes hacen afirmaciones sin qualifier.

### 3.3 Impactos INDETERMINADO

Si AG-09 produjo uno o más impactos con `significancia: INDETERMINADO`:

```markdown
### C.3.X. IMP-XX — [Nombre del impacto] — ⚠️ INDETERMINADO

**Factor receptor**: FR-XX  
**Acciones causantes**: A-XX  
**Estado de evidencia**: INDETERMINADO — ver GAP-XXX

El impacto sobre este factor no puede valorarse con los datos disponibles en la fase de gabinete. 
El gap que bloquea la valoración es GAP-XXX ([descripción del gap]). 
La valoración quedará determinada cuando se resuelva el gap, en la fase de expediente real.

> **Nota**: Este impacto figura en el expediente como INDETERMINADO, no como Compatible ni como ausente. 
> Cualquier interpretación del órgano ambiental debe tener en cuenta esta limitación explícita.
```

Nunca se sustituye INDETERMINADO por una valoración a la baja ("dado que el contexto es industrial, probablemente Compatible"). La valoración provisional no existe.

---

## §4. Cómo redactar impactos según su significancia

### 4.1 Impactos Compatibles y Compatibles residuales

La diferencia entre Compatible y Compatible residual debe ser visible en la descripción:
- **Compatible**: el impacto produce alteración menor incluso sin medidas específicas intensivas; las medidas preventivas estándar son suficientes.
- **Compatible residual**: sin medidas el impacto sería mayor; es la aplicación de medidas la que lo lleva por debajo del umbral de preocupación.

Formulación de cierre para Compatible residual:
> "Con la aplicación de [medida/s], la significancia residual se reduce a Compatible residual. Sin dichas medidas, la significancia sería [nivel sin medidas]."

Nunca: "el impacto es insignificante" ni "el impacto es nulo". Compatible residual no es nulo.

### 4.2 Impactos Moderados

El impacto Moderado es el de mayor nivel que puede cerrar un expediente de EIA simplificada sin reformulación del proyecto (si tiene medida eficaz que lo reduce a Compatible). Requiere tratamiento más detallado que los Compatibles:

1. Describir el mecanismo del impacto con más detalle (por qué alcanza Moderado y no Compatible)
2. Justificar explícitamente la reducción a Compatible con las medidas propuestas
3. Referencia PVA obligatoria para confirmar la eficacia de las medidas
4. Nota de condicionante normativo si hay normativa específica aplicable

Formulación estándar de apertura para Moderado:
> "Este es el impacto de mayor significancia sin medidas identificado en el expediente. [Descripción del mecanismo]. Con las medidas [M-XX, M-XX, M-XX], la significancia se reduce a Compatible."

No marcar como Moderado con un emoji y luego describirlo con la misma ligereza que los Compatibles — el Moderado requiere la mayor densidad descriptiva del bloque.

### 4.3 Impactos Severos

Si AG-09 produce un impacto Severo (no ocurrió en el piloto, pero puede ocurrir en otros expedientes):
- La descripción debe ser más extensa que para Moderado
- Las medidas deben describirse con detalle de eficacia esperada
- Si la significancia residual no baja de Severo incluso con medidas: señalarlo explícitamente
- Nunca suavizar la descripción de un Severo para que "suene menos preocupante"

### 4.4 Impactos Críticos

Si AG-09 produce un impacto Crítico: el Bloque C lo describe con exactitud y añade una nota visible:
> **Nota**: Este impacto tiene significancia Crítica, lo que implica incompatibilidad con la tramitación del proyecto sin reformulación profunda del mismo o aplicación de medidas compensatorias de eficacia demostrada. El órgano ambiental deberá valorar su aceptabilidad.

El Bloque C no puede suavizar un Crítico ni proponer medidas que no están en AG-09 como solución.

### 4.5 Impactos positivos

Los impactos positivos tienen la misma estructura que los negativos (factor receptor + acciones + tabla Conesa con signo positivo + descripción) con estas diferencias:
- No tienen `significancia_residual` separada (no hay medidas correctoras que los reduzcan)
- La descripción debe ser técnica y referenciada, no laudatoria
- No se usa "contribuye al desarrollo sostenible" ni frases sin factor receptor
- La significancia positiva se expresa en la misma escala, con sentido inverso

Formulación de cierre para impacto positivo:
> "El impacto positivo sobre [factor receptor] tiene significancia [nivel]."

No: "contribuye positivamente al medio ambiente", "tiene un impacto muy beneficioso", "demuestra el compromiso del promotor con la sostenibilidad".

### 4.6 Condicionantes transversales

Un condicionante transversal (PRL, seguridad vial, normativa sanitaria laboral) se registra en el Bloque C con una estructura específica que lo distingue de los impactos nucleares:

```markdown
### C.3.X. [Nombre] — Condicionante transversal [ámbito]

**Tipo de registro**: CONDICIONANTE TRANSVERSAL — no impacto nuclear del análisis ambiental.

[Descripción de por qué está registrado y qué instrumento normativo es competente]

[Si hay co-beneficio de las medidas ambientales sobre este condicionante: describir el co-beneficio,
precisando que no altera la escala del análisis EIA]
```

El condicionante no puede convertirse en un impacto EIA, ni puede desaparecer del bloque porque "no es propiamente ambiental". Se registra, se diferencia, y se indica el instrumento competente.

---

## §5. Cómo redactar la influencia de las medidas

### 5.1 La medida reduce, no elimina

La formulación "con las medidas propuestas, el impacto queda eliminado" está prohibida. Las medidas reducen la significancia; no producen impacto nulo.

La formulación correcta:
- "Con la aplicación de M-XX, la significancia se reduce de [sin medidas] a [residual]."
- "Las medidas M-XX, M-XX y M-XX actúan sobre [mecanismo] y permiten alcanzar una significancia residual de [nivel]."

### 5.2 Descripción proporcional a la eficacia

Si la medida reduce de Moderado a Compatible: merece un párrafo de justificación de la eficacia (por qué esas medidas son suficientes para esa reducción).

Si la medida reduce de Compatible a Compatible residual: una frase es suficiente.

Si las medidas no reducen la significancia (IMP-05 en el piloto: Compatible → Compatible): indicar explícitamente que las medidas mantienen controlado el impacto sin reducir su nivel.

### 5.3 Las medidas no pueden nombrarse sin procedencia

Cada medida citada en el Bloque C (M-XX) existe en `impactos/medidas_correctoras.json`. No se pueden inventar medidas en el bloque narrativo que no estén en ese archivo.

### 5.4 El PVA confirma, no resuelve

Las referencias al PVA en el Bloque C son para indicar que existe seguimiento que confirmará la eficacia de las medidas. El PVA no resuelve el impacto — lo vigila. La formulación:
- Correcta: "El indicador PVA-01 permitirá confirmar la eficacia de las medidas durante la vida activa de la instalación."
- Incorrecta: "El impacto quedará controlado mediante PVA-01."

---

## §6. La tabla resumen C.4 y el párrafo de conclusión

### 6.1 La tabla resumen

La tabla de la sección C.4 tiene columnas obligatorias:
- ID (IMP-XX)
- Denominación
- Significancia sin medidas
- Significancia con medidas (o "fuera de escala" para condicionantes transversales)
- Medidas aplicadas (M-XX)

Para impactos positivos: una sola columna de significancia (no aplica "sin medidas" separado).
Para INDETERMINADO: la columna de significancia muestra "INDETERMINADO — GAP-XXX".

### 6.2 El párrafo de conclusión

El Bloque C puede incluir un párrafo conclusivo al final de la tabla, pero con restricciones estrictas:

**Permitido**:
- Indicar qué impacto tiene la significancia más alta antes de medidas
- Indicar que todos los impactos negativos quedan en [nivel] o inferior con las medidas propuestas
- Indicar si hay impactos INDETERMINADO pendientes de resolución de gap

**Prohibido**:
- "El balance ambiental neto es positivo" — es un juicio de valor sobre el conjunto del proyecto que no pertenece al análisis de impactos
- "El proyecto es ambientalmente viable" — eso lo dice el órgano ambiental, no el DA
- "Los impactos son todos bajos o inexistentes" — Compatible residual no es inexistente
- Cualquier frase que suene como argumento de defensa del proyecto

La frase conclusiva válida se limita a describir el rango de significancias: "De los impactos negativos identificados, el de mayor significancia es IMP-XX con [nivel] antes de medidas, reducido a [nivel residual] con las medidas propuestas."

---

## §7. Tratamiento específico del IMP-01 (caso piloto: único Moderado)

El IMP-01 del piloto Recimetal (emisión de partículas metálicas) es el único impacto que alcanza Moderado antes de medidas. Este caso ilustra la regla general para el impacto de mayor significancia del expediente:

1. **Posición en el bloque**: siempre en primer lugar (o primero entre los nucleares negativos) — el órgano ambiental busca el impacto más significativo primero.
2. **Marcador visual**: una nota o header diferenciado que lo identifique como el de mayor significancia (sin emoji — una nota en blockquote o asterisco en la tabla es más robusto).
3. **Descripción más densa**: el mecanismo (viento + acopios + dispersión SO) debe estar completo con referencias a los datos climáticos de AG-07 (velocidad media, días con rachas >55 km/h, dirección predominante).
4. **Justificación de la reducción**: por qué M-01 + M-02 + M-03 son suficientes para reducir de Moderado a Compatible — no basta con listarlas, hay que explicar el mecanismo.
5. **El qualifier R1203=0**: es el contexto que explica por qué Moderado y no Severo. Debe estar en la descripción, no como justificación de por qué no preocupa sino como dato técnico del objeto evaluado que determina la intensidad.

Lo que el piloto hizo bien: incluir la referencia a los datos climáticos (22,5 km/h, 99,2 días) y mencionar el mecanismo de dispersión hacia SO. Eso es lo que convierte la descripción en técnicamente defendible.

Lo que puede mejorarse: la frase "Sin trituración ni corte (R1203=0), la generación de partículas es significativamente menor que en instalaciones con línea activa" usa "significativamente menor" como comparación relativa. La valoración debe ser absoluta (qué produce esta instalación) más que comparativa (qué produciría con R1203>0). La comparación es contexto útil; no debería estar en la sección "Justificación" sino en la descripción del mecanismo.

---

## §8. Diferencia modo test vs expediente real

| Aspecto | Modo TEST | Expediente REAL |
|---------|-----------|-----------------|
| Impactos INDETERMINADO | Aceptados con nota y GAP | Deben resolverse antes de presentación |
| Qualifiers de gabinete en impactos | Presentes y visibles | Ídem — si hay campo, actualizar la certeza |
| IMP-06 con precaución por falta de campo | Aceptado con blockquote precaución | Prospección de campo requerida |
| Significancias de AG-09 | Se usan directamente | Ídem |
| Párrafo conclusivo con "balance positivo" | Prohibido en ambos modos | Prohibido en ambos modos |
| Medidas de AG-09 no verificadas in situ | Aceptado en test | Verificación del estado real de las medidas |

El gate 7 (bloque C) en modo TEST se satisface si:
- Los apartados C.1, C.2, C.3 y C.4 están presentes
- La tabla C.4 tiene columnas de significancia sin y con medidas
- Ningún impacto ha cambiado su significancia respecto a AG-09
- Los qualifiers de ag-09 están en el texto de la descripción de cada impacto
- Los impactos INDETERMINADO, si los hay, están visibles con referencia al gap

---

## §9. Estructura mínima obligatoria

```markdown
# BLOQUE C — Identificación y valoración de impactos ambientales

## C.1. Metodología
[Conesa simplificado + escala de 5 niveles + criterio de proporcionalidad al tipo de EIA]
[Referencia explícita: los valores Conesa derivan de AG-09 (identificacion_valoracion_impactos.json)]

## C.2. Acciones del proyecto
[Tabla ID / Descripción / Fase — extraída de AG-09]

## C.3. Valoración detallada de impactos
[Un apartado por cada IMP-XX identificado en AG-09]
[Orden: primero el/los de mayor significancia, luego el resto de nucleares negativos,
 luego condicionantes transversales, luego positivos]

### C.3.1. [IMP de mayor significancia]
**Factor receptor**: FR-XX
**Acciones causantes**: A-XX
[Descripción con qualifiers]
| Tabla Conesa |
[Justificación si la significancia sin medidas es Moderada o superior]
[Medidas + PVA]

... [resto de IMPs] ...

### C.3.X. [Condicionantes transversales]
**Tipo de registro**: CONDICIONANTE TRANSVERSAL — [ámbito]
[Descripción + instrumento competente + co-beneficio si aplica]

### C.3.X+1. [Impactos positivos]
**Factor receptor**: FR-XX
[Tabla Conesa con signo positivo]
[Descripción técnica sin frases laudatorias]

## C.4. Tabla resumen de impactos
[ID / Denominación / Sig. sin medidas / Sig. con medidas / Medidas]
[Párrafo conclusivo limitado a describir el rango de significancias]
```

---

## §10a. Reglas incorporadas del segundo piloto (Nave 222 — 2026-04-19)

**Origen**: OBS-M12-003, OBS-M12-004, OBS-M12-006, OBS-M12-007 del postmortem comparativo.

### Regla adicional C-9: Conesa para todos los impactos (OBS-M12-003)
IMP-012 e IMP-013 en Nave 222 se redactaron sin tabla Conesa. Esto hace el expediente vulnerable: el órgano ambiental puede cuestionar la base de la calificación de impactos Compatible. A partir de esta regla, todos los impactos — incluyendo los de significancia Compatible — deben tener tabla o desglose de parámetros.

### Regla adicional C-10: Sección C.5 acumulativos (OBS-M12-004)
El Bloque C de Nave 222 no incluye sección de acumulativos/sinérgicos. Artículo 45 de la Ley 21/2013 lo exige. La sección es obligatoria incluso si la conclusión es "no se identifican efectos acumulativos relevantes en modo gabinete".

### Regla adicional C-11: Cadenas condicionales (OBS-M12-007)
CONT-005 (VFU / LER 16 01 06) en Nave 222 no activaba ningún análisis de impactos condicionales en el Bloque C. Si CONT-005 se confirma (la instalación recibe VFU), se activa RD 265/2021 y la obligación de operar como CAT, con impactos adicionales no analizados. La regla C-11 fuerza a que cada CONT no resuelto con impacto potencial en el perfil ambiental genere un bloque condicional visible en C.

### Regla adicional C-12: Gap ALTA en impacto positivo (OBS-M12-006)
GAP-006 (flujo ambiguo de LER 19 12 03) afecta a IMP-P01 (valorización de cobre) pero no aparece en el apartado de IMP-P01 en el Bloque C. La regla C-12 exige que si un gap ALTA afecta a la cuantificación de un impacto positivo, la incertidumbre debe aparecer junto a ese impacto.

## §10. Lecciones del piloto Recimetal

### L-01: Lo que funcionó bien y se codifica como obligatorio

**Estructura por impacto**: un apartado numerado por cada IMP, con cabecera consistente (factor receptor + acciones causantes) y tabla Conesa en cada uno. Esto hace el bloque trazable y auditable.

**Condicionante transversal IMP-08 con apartado propio**: identificado explícitamente como fuera de la escala EIA, con la referencia al instrumento competente (Ley 31/1995 PRL) y el co-beneficio documentado. Patrón a mantener.

**Qualifiers heredados en IMP-06**: "No se detectan especies protegidas en las fuentes consultadas en modo gabinete, pero la prospección de campo no ha sido realizada" — exactamente el nivel de certeza de la ficha AG-08. Patrón a mantener.

**Blockquote de precaución en IMP-06**: visible, con referencia a los gaps. Patrón a mantener.

**IMP-01 como primer apartado de la sección**: posición correcta para el impacto de mayor significancia.

### L-02: Riesgos de deriva redaccional identificados en el piloto

**C.4 conclusión: "El balance ambiental neto es positivo"**: esta frase supera lo que la tabla muestra. El balance no es un resultado técnico de la metodología Conesa — es una interpretación del redactor. En v2.1 esta frase está prohibida. La conclusión se limita a describir el rango de significancias.

**IMP-04 ruido: comparación relativa como argumento**: "el nivel sonoro es comparable al de cualquier actividad logística en polígono industrial" — usar la comparación como argumento de minimización es un drift redaccional. En v2.1: el contexto de polígono industrial se menciona como dato de la ficha AG-08 (sensibilidad del receptor), no como argumento de que el impacto "no importa tanto".

**IMP-10 CO2: "ahorro significativo"**: uso informal del término "significativo" en un contexto técnico EIA donde tiene significado específico. En v2.1: usar "apreciable", "relevante" o cuantificar; reservar "significativo" para la escala Conesa.

**IMP-01 justificación: comparación relativa**: "significativamente menor que en instalaciones con línea activa" — la valoración debe ser absoluta, no comparativa. La referencia a R1203=0 es contexto del objeto evaluado, no argumento relativo.

### L-03: Qué debe blindarse

**La doble columna de significancia en la tabla C.4**: garantiza que "Compatible residual" no desaparezca en la lectura rápida. Si solo hubiera una columna de "significancia final", el lector podría perder de vista que el impacto era Compatible sin medidas.

**El qualifier del modo gabinete en impactos de flora/fauna**: IMP-06 tiene el blockquote de precaución. Si el redactor lo suprime "porque suena repetitivo con el Bloque B", se pierde la visibilidad en el bloque de valoración. El blockquote de precaución debe estar tanto en Bloque B (inventario) como en Bloque C (valoración de impacto sobre ese factor).

**El párrafo de conclusión C.4**: es el punto más vulnerable del bloque. El redactor siente la presión de hacer una síntesis positiva para ayudar a la aprobación. La regla es clara: la síntesis describe el rango, no interpreta el balance.
