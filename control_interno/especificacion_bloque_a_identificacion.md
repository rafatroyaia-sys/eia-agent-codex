# Especificación técnica — AG-10 / Bloque A: Identificación y descripción del proyecto
**Versión**: 2.1  
**Estado**: VALIDADO  
**Fecha**: 2026-04-15  
**Baseline**: piloto-recimetal + criterios P2

---

## §1. Qué es un Bloque A válido en este sistema

El Bloque A es la **descripción oficial del proyecto y del promotor** en el Documento Ambiental. No es un resumen de los documentos del promotor. Es la versión verificada, delimitada y trazable de esos documentos, con los estados de evidencia visibles y el objeto evaluado exactamente como AG-04 lo cerró.

Un Bloque A es válido si y solo si:

1. **Reproduce el objeto evaluado cerrado**: cada dato estructural del bloque (promotor, emplazamiento, operaciones, equipos, capacidades, fases) deriva directamente de `hechos_confirmados.json` o de los documentos del promotor con estado de evidencia explícito.
2. **Mantiene los estados de evidencia visibles**: los datos DECLARADOS siguen siendo DECLARADOS en el texto; los pendientes no desaparecen en una redacción más fluida.
3. **No amplía el alcance de AG-04**: las operaciones excluidas en el cierre del objeto siguen excluidas en la prosa. Las instalaciones vinculadas no se incorporan al objeto evaluado.
4. **Trata la dependencia funcional sin resolver la cautela de fraccionamiento**: si la instalación tiene vinculación funcional con otras instalaciones, se describe exactamente con las palabras del cierre AG-04, sin resolver la cautela ni ignorarla.
5. **No anticipa valoraciones de impacto**: ninguna oración del Bloque A evalúa impactos, predice efectos o anticipa compatibilidad ambiental. Eso corresponde al Bloque C.
6. **Los gaps activos de AG-04 permanecen visibles**: un gap relevante para la descripción del proyecto (ej: plano de delimitación no aportado, compatibilidad urbanística no acreditada) no se absorbe en la redacción.

Lo que el Bloque A **no es**:
- No es el lugar para ampliar la descripción del conjunto operativo más allá del objeto evaluado
- No es el lugar para justificar por qué los impactos serán bajos o inexistentes
- No es el lugar para resolver cautelas o contradicciones que AG-04 dejó abiertas
- No es el lugar para añadir equipos, procesos o capacidades que no están en el objeto evaluado cerrado

---

## §2. Relación exacta entre AG-04 y Bloque A

El Bloque A es la traducción narrativa del cierre del objeto evaluado de AG-04. La relación es unidireccional:

```
AG-04 (cierre del objeto evaluado) → AG-10/bloque_A (descripción del proyecto)
```

La fuente primaria de cada dato es `capas/hechos_confirmados.json` (HCs de categorías: promotor, emplazamiento, procedimiento, actividad, operaciones, equipos). Los documentos del promotor (DOC-XXX) son la fuente original que AG-02 extrajo y AG-04 cerró; no se vuelven a interpretar en esta fase.

### Correspondencia de campos

| Categoría HC | Sección Bloque A |
|--------------|------------------|
| `promotor` | A.1 — Identificación del promotor |
| `tecnico_redactor` | A.2 — Técnico redactor |
| `emplazamiento` | A.3 — Localización |
| `procedimiento` | A.3 + A.7 — Encuadre procedimental |
| `actividad` | A.4 — Descripción del proyecto |
| `operaciones` | A.4.2 (incluidas) + A.4.3 (excluidas) |
| Equipos (de HC de equipos) | A.5 — Equipos e infraestructuras |
| Fases (de HC de fases) | A.6 — Fases del proyecto |
| GAPs del objeto evaluado | Notas en secciones correspondientes |
| Cautelas del objeto evaluado | A.8 — Relación con otras instalaciones |

**Regla de trazabilidad**: cada dato estructural del Bloque A puede trazarse a un HC-XXX específico. Si no puede trazarse a un HC, no puede incluirse en el Bloque A.

---

## §3. Herencia del estado de evidencia

El estado de evidencia de los HCs de AG-02/AG-04 se hereda directamente en el Bloque A. La tabla de traducción a formato narrativo:

| Estado HC | Formulación en Bloque A | Formato recomendado |
|-----------|------------------------|---------------------|
| CONFIRMADO | Sin qualifier; afirmación directa | Columna "Estado" = CONFIRMADO; o afirmación directa en texto |
| DECLARADO | "Declarado por el promotor en [fuente]" / "[valor] (declarado, fuente única: [doc])" | Columna "Estado" = DECLARADO con fuente; o nota al pie |
| INFERIDO | "Se infiere a partir de [dato]..." | Nota con qualifier; no como dato directo |
| ESTIMADO | "Se estima, a partir de [metodología]..." | Nota con qualifier |
| PENDIENTE | No incluir como dato; registrar como gap | Nota GAP-XXX o advertencia |
| DESCARTADO | No incluir | — |

**Para datos de identificación estructural** (promotor, RC, coordenadas, superficie, capacidades): usar tablas con columna `Estado evidencia`. Esta columna no es decorativa — es parte del documento.

**Para datos DECLARADOS con una sola fuente** (típicamente: coordenadas, NIF, algunos datos de capacidad): indicar explícitamente "fuente única: [doc]" para que el lector técnico sepa que no fue contrastado.

---

## §4. Tratamiento de cada componente del Bloque A

### 4.1 Promotor

Datos de la tabla HC (HC-001 a HC-005 y similares):
- Razón social, NIF, representante legal, domicilio social.
- Si hay datos DECLARADOS (NIF, etc.): señalarlo en la columna Estado de la tabla.
- Si existe una autorización previa relevante (ej: resolución anterior de la actividad): referenciarla con su estado (DECLARADO si no se ha aportado copia, CONFIRMADO si se tiene el documento).

No incluir: datos de las naves vinculadas, datos del conjunto operativo, datos de otras instalaciones del mismo promotor.

### 4.2 Técnico redactor

Nombre, titulación, colegiación. Estado CONFIRMADO si aparece en los documentos aportados.
Referencia al art. 16 de la Ley 21/2013 si la titulación es relevante para acreditar la capacidad técnica del redactor.
No confundir el técnico redactor del DA con el técnico ambiental del promotor.

### 4.3 Localización

Dos sub-secciones:

**A.3.1 Datos de localización**: tabla con RC, dirección catastral, municipio, isla, provincia, CP, coordenadas (WGS84 y UTM), contexto territorial. Columna Estado evidencia para cada fila.

**Coordenadas**: si son DECLARADO (fuente única: promotor), así debe constar. El hecho de que AG-06 las haya usado para generar mapas no las convierte en CONFIRMADO — son el punto de trabajo aceptado mientras no se obtenga contraste independiente (Catastro georreferenciado, coordenadas GRAFCAN verificadas). Añadir nota si la verificación cartográfica independiente confirmó la coherencia.

**A.3.2 Superficie**: distinguir siempre entre:
- Superficie de la finca catastral matriz (total de la RC)
- Superficie material evaluada (la parte que es objeto del expediente)

Si la delimitación exacta no ha sido aportada como plano georreferenciado, registrar el gap con nota en blockquote. La superficie material evaluada puede ser CONFIRMADO aunque la delimitación precisa sea DECLARADO provisional (son datos distintos).

### 4.4 Actividad

**A.4.1 Objeto y naturaleza**: descripción precisa de qué hace la instalación. Usar la formulación de AG-04, no la del promotor sin filtro.

Tres obligaciones para instalaciones con dependencia funcional:
1. Describir el papel específico de la instalación evaluada (qué hace ella, sin el conjunto)
2. Nombrar la vinculación funcional explícitamente ("instalación exterior vinculada a...")
3. Declarar que las instalaciones vinculadas tienen procedimientos independientes

No describir lo que hace el conjunto operativo como si lo hiciera la instalación evaluada.

**Sobre la exclusión de operaciones intensivas** (si aplica): si AG-04 cerró que determinadas operaciones con mayor impacto potencial (trituración, corte, compactación, etc.) no se realizan en la instalación evaluada, esto debe constar en la descripción. Es un dato del objeto evaluado, no una anticipación de impactos. El Bloque C usará este dato para valorar los impactos.

La diferencia entre describir y valorar:
- "La instalación no dispone de equipos de trituración ni corte (R1203 = 0 en el objeto evaluado)" → descripción [correcto en Bloque A]
- "Por ello, los impactos acústicos serán bajos" → valoración [incorrecto en Bloque A, va en Bloque C]

### 4.5 Operaciones incluidas y excluidas

Esta es la sección más crítica del Bloque A para la coherencia del expediente. Un error aquí (operación colada o excluida incorrectamente) se propaga a todos los bloques posteriores.

**A.4.2 Operaciones incluidas**: tabla con:
- Código legal base (R12, R13, D15...)
- Código operativo interno (R1201, R1302...)
- Descripción
- Capacidad
- Estado de evidencia

Las capacidades deben expresarse exactamente como están en los HCs: cantidad + unidad + período (t/día, t/año, t simultáneas, etc.). No redondear ni simplificar.

**A.4.3 Operaciones excluidas**: tabla con:
- Operación / código
- Motivo de exclusión

Esta tabla es obligatoria siempre que AG-04 haya excluido operaciones del alcance. Su propósito es triple:
1. Delimitar el alcance frente al promotor
2. Delimitar el alcance frente al órgano ambiental
3. Proteger al expediente frente a interpretaciones expansivas

Si la exclusión se basó en la resolución de una contradicción documental (como CONT-001 en el piloto), la tabla de exclusiones refleja el resultado resuelto (R1203 = 0 en la parcela), y la nota de trazabilidad de la contradicción queda en `inferencias_y_gaps.json`, no en el Bloque A. El Bloque A declara el estado; la trazabilidad de cómo se llegó al estado está en las capas.

### 4.6 Equipos incluidos y excluidos

**Equipos incluidos**: tabla con equipo, descripción técnica, función. Si los datos técnicos (potencia, capacidad, homologación) provienen de los documentos del promotor: estado DECLARADO.

**Equipos excluidos**: si AG-04 identificó que determinados equipos del conjunto operativo no están en la instalación evaluada (ej: sierra angular, prensa, triturador), listarlos brevemente para reforzar la delimitación.

**Infraestructuras**: tabla con elemento, descripción, estado. Las infraestructuras declaradas por el promotor (solera, cerramiento, drenaje) son DECLARADO hasta que haya plano o inspección.

**Recursos compartidos**: si la instalación comparte recursos con otras instalaciones (báscula, personal, sistema administrativo), describirlos en un apartado específico. Esto es parte del objeto evaluado cerrado y es relevante para comprender la escala real de la actividad.

### 4.7 Dependencia funcional

La dependencia funcional merece un tratamiento específico porque genera dos riesgos opuestos:

**Riesgo de expansión**: describir las naves vinculadas como si fueran parte del objeto evaluado; usar su capacidad o sus operaciones para describir la instalación; sonar como si el expediente cubriera el conjunto.

**Riesgo de minimización**: ignorar la vinculación funcional y presentar la instalación como completamente autónoma, cuando en realidad comparte escala, personal y control documental con el conjunto.

La formulación correcta: "La [instalación evaluada] actúa como [su función específica] vinculada funcionalmente al conjunto operativo [nombre/referencia]. Esta vinculación es relevante para [aspecto procedimental]. Las instalaciones vinculadas tienen tramitación ambiental y sectorial independiente."

No resolver la cautela de fraccionamiento en el Bloque A: si AG-05 registró CAUTELA sobre posible fraccionamiento del proyecto, el Bloque A la referencia como existente. No dice "no hay fraccionamiento"; no dice "hay fraccionamiento grave". Dice "esta cautela fue analizada en el triaje normativo y se registra como CAUTELA-XXX no bloqueante en modo test" (o el estado que corresponda).

### 4.8 Fases del proyecto

Tabla con:
- Fase (nombre)
- Descripción (qué se hace en cada fase)
- Duración prevista

Si la duración es indeterminada (explotación continuada sin límite), así consta. No inventar duraciones. Si no hay datos sobre la fase de cese (común en instalaciones en funcionamiento), declararlo.

La fase de adecuación / instalación previa al inicio de la actividad es relevante porque en ella se ejecutan las medidas preventivas del PVA. Si AG-09 registró medidas para la fase de instalación, deben ser coherentes con la descripción de la fase aquí.

### 4.9 Compatibilidad urbanística

Tratamiento obligatorio por dos razones:
1. La compatibilidad urbanística es un requisito legal del DA (art. 16 Ley 21/2013)
2. En expedientes sobre suelo con clasificación catastral histórica ambigua, la distinción entre clasificación catastral y calificación urbanística es crítica

Dos cosas que siempre deben aparecer:
1. El estado de evidencia de la compatibilidad (CONFIRMADO si hay certificado municipal, DECLARADO si solo lo dice el promotor, PENDIENTE si falta el certificado)
2. Si hay alguna discrepancia entre la clasificación catastral y la calificación urbanística: explicarla sin resolver lo que no se ha resuelto

Lo que no puede decirse si la compatibilidad es DECLARADO o PENDIENTE: "la actividad es urbanísticamente compatible" — eso solo puede afirmarse con certificado o con referencia normativa expresa al planeamiento vigente.

### 4.10 Encuadre procedimental

Tipo de evaluación (simplificada / ordinaria), base legal (art. y ley), órgano ambiental, órgano sustantivo. Si coinciden, indicarlo.

Si la no sujeción a otros procedimientos (AAI, ICA, etc.) está confirmada en los documentos: registrarla como CONFIRMADO.

---

## §5. Afirmaciones prohibidas

| Formulación prohibida | Por qué | Alternativa correcta |
|-----------------------|---------|----------------------|
| "El proyecto no genera impactos significativos" | Valoración de impacto — va en Bloque C | Eliminar del Bloque A |
| "La actividad es compatible con el entorno" | Valoración — va en Bloque C o D | Eliminar del Bloque A |
| "Los impactos serán bajos/nulos porque [descripción]" | Anticipa valoración | Describir el hecho técnico; la valoración va en Bloque C |
| Incluir operaciones de naves vinculadas en A.4.2 | Amplía el objeto más allá de AG-04 | Solo operaciones del objeto evaluado cerrado |
| "El conjunto operativo gestiona X t/año" si X incluye las naves | Confunde alcances | "La instalación evaluada tiene capacidad de X t/año" |
| Distancias o capacidades del conjunto como si fueran de la parcela | Mezcla de alcances | Datos exclusivos del objeto evaluado cerrado |
| "[Dato DECLARADO] es correcto" | Eleva DECLARADO a CONFIRMADO | "[Dato DECLARADO] (declarado por el promotor en [fuente])" |
| Omitir la columna Estado evidencia en tablas de datos de identificación | Hace invisibles los estados de evidencia | Columna Estado en todas las tablas de identificación |
| "Sin impacto sobre [factor]" en la descripción del proyecto | Valoración anticipada | Descripción técnica del equipo/operación sin valorar |
| "Se descarta la necesidad de..." (ej: medidas, consultas) | Valoración anticipada | No incluir; si es necesario, va en Bloque C o Bloque D |

---

## §6. Modo test vs expediente real

| Aspecto | Modo TEST | Expediente REAL |
|---------|-----------|-----------------|
| GAP-001 (compatibilidad urbanística no acreditada) | Permitido como DECLARADO con nota | Requiere certificado o referencia normativa al PGOU |
| GAP-006 (plano de delimitación no aportado) | Superficie material CONFIRMADO; geometría DECLARADO provisional | Plano georreferenciado obligatorio |
| Coordenadas DECLARADO | Aceptado como base de trabajo | Verificar con Catastro georreferenciado o contraste WMS |
| CONT-001 (contradicción documental resuelta) | Aceptado con nota de trazabilidad en inferencias_y_gaps.json | Requiere declaración formal del promotor o anejo corregido |
| Cautelas sobre fraccionamiento | Registradas como no bloqueantes | Análisis normativo formal del fraccionamiento si aplica |
| Recursos DECLARADO sin anejo técnico | Permitido con nota y GAP | Anejo técnico requerido para infraestructuras críticas (drenaje) |

En modo TEST, el gate 7 (bloque A) se considera satisfecho si:
- Los 8 apartados obligatorios están presentes
- Los datos estructurales tienen columna de estado de evidencia visible
- Las operaciones excluidas tienen tabla explícita
- Los GAPs activos tienen nota visible en el apartado correspondiente
- No hay valoraciones de impacto filtradas

---

## §7. Estructura mínima obligatoria

```markdown
# BLOQUE A — Identificación del promotor y descripción del proyecto

**Modo**: [TEST / PRODUCCIÓN] — [gaps activos si los hay]

## A.1. Identificación del promotor
[Tabla con razón social, NIF, representante, domicilio — columna Estado evidencia]

## A.2. Identificación del técnico redactor
[Nombre, titulación, colegiación — referencia art. 16 Ley 21/2013 si aplica]

## A.3. Localización del proyecto
### A.3.1. Datos de localización
[Tabla con RC, dirección, municipio, isla, CP, coordenadas WGS84 y UTM — columna Estado evidencia]
### A.3.2. Superficie
[Tabla distinguiendo finca catastral vs superficie evaluada — con nota GAP si aplica]

## A.4. Descripción del proyecto
### A.4.1. Objeto y naturaleza de la actividad
[Descripción de lo que hace la instalación evaluada + vinculación funcional si aplica]
### A.4.2. Operaciones incluidas en el objeto evaluado
[Tabla con códigos legal/operativo, descripción, capacidad, estado]
### A.4.3. Operaciones expresamente excluidas del objeto evaluado
[Tabla con operación excluida + motivo — obligatoria si hay exclusiones en AG-04]
### A.4.4. Residuos/materias admitidos [si aplica]
[Tabla con códigos LER o materias, capacidades, estado]

## A.5. Equipos e infraestructuras
### A.5.1. Equipos incluidos
[Tabla con equipo, descripción técnica, función]
### A.5.2. Infraestructuras
[Tabla con elemento, descripción, estado]
### A.5.3. Recursos compartidos con instalaciones vinculadas [si aplica]
[Descripción de qué se comparte y con quién]

## A.6. Fases del proyecto
[Tabla con fase, descripción, duración]

## A.7. Compatibilidad urbanística
[Estado de acreditación con nota GAP si no está acreditada]

## A.8. Relación con otras instalaciones y procedimientos
[Vinculación funcional + cautelas registradas en AG-05 + encuadre procedimental]
```

---

## §8a. Regla de visibilidad de gaps ALTA sobre identidad — OB-04 (incorporado 2026-04-19)

**Origen**: OBS-M12-001 + OBS-M12-005 del postmortem comparativo Parcela vs Nave 222.

**Problema identificado**: en Nave 222, GAP-004 (cambio de titularidad en tramitación) era visible en Bloque I y en las capas internas, pero no en el Bloque A.1 donde el lector del DA identifica al promotor. El DA identificaba al promotor sin advertir que ese dato estaba cuestionado. Similar para el uso catastral "almacén agrario" (Catastro) vs uso industrial real.

**Regla incorporada**: todo gap ALTA sobre identidad debe tener nota visible en el apartado del Bloque A donde ese dato aparece — no solo en las conclusiones o en las capas.

**Supuestos cubiertos**:

| Gap de identidad | Lugar en Bloque A | Formato |
|-----------------|-------------------|---------|
| Cambio de titularidad en tramitación | A.1 (Promotor) | Blockquote con GAP-XXX y acción pendiente |
| Uso catastral histórico distinto al real | A.3.1 (Localización) | Fila en tabla con estado CONFIRMADO (Catastro) + nota de divergencia |
| Discrepancias de superficie entre fuentes | A.3.2 (Superficie) | Tabla con TODAS las magnitudes y sus fuentes; nota GAP si aplica |
| Coordenadas sin verificación independiente | A.3.1 | Estado DECLARADO visible; nota si AG-06 confirmó coherencia (no eleva a CONFIRMADO) |
| Título habilitante sin texto | A.1 o A.8 | Estado REFERENCIADA + acción requerida |

**Autochequeo adicional (ítem 9 y 10 del prompt de bloque)**:
- ¿Hay algún gap ALTA sobre titularidad, uso catastral o coordenadas? ¿Tiene nota visible en A.1 o A.3.1?
- ¿El uso catastral aparece en A.3.1 con estado de evidencia y nota si difiere del uso real?

## §8. Lecciones del piloto Recimetal

### L-01: Lo que funcionó bien y se codifica como obligatorio

**Tablas con columna "Estado evidencia"**: en A.1, A.3.1, A.3.2, A.4.2, A.5.1, A.5.2. Este formato hace que los estados de evidencia sean imposibles de ignorar para el lector técnico. Es el mecanismo principal de control de la paridad de certeza en el Bloque A.

**Tabla de operaciones excluidas (A.4.3)**: sección explícita, con tabla, con motivo de exclusión. La exclusión de R1203 en el piloto es el elemento de mayor impacto en la valoración de impactos acústicos y de polvo. Sin esta tabla explícita, el expediente sería vulnerable a interpretaciones que incluyeran esas operaciones.

**Nota GAP en blockquote para datos críticos pendientes**: A.3.2 (GAP-006 sobre delimitación) y A.7 (GAP-001 sobre compatibilidad urbanística) tienen notas visibles en blockquote. Patrón a mantener.

**A.5.3 Recursos compartidos**: apartado específico para la dependencia funcional. Ni la ignora (riesgo de minimización) ni incorpora las naves al objeto evaluado (riesgo de expansión). Correcto.

**A.8 con cautelas referenciadas**: las cautelas de AG-05 (CAUTELA-001 y CAUTELA-002) aparecen en A.8 como registradas y no bloqueantes en modo test. No se resuelven en el Bloque A; se declaran.

### L-02: Partes más delicadas del piloto

**Coordenadas DECLARADO usadas operativamente**: en A.3.1 el texto dice "Las coordenadas declaradas han sido trasladadas al GeoJSON y a los servicios WMS consultados en Fase 4". Esto puede dar la impresión de que la traslación operativa valida las coordenadas. En v2.1 la formulación debe distinguir entre "usadas como base de trabajo" y "verificadas de forma independiente". Si AG-06 confirmó coherencia cartográfica, se puede añadir una nota de coherencia, pero el estado HC-012/HC-013 sigue siendo DECLARADO hasta contraste formal.

**A.4.1: descripción de la actividad que roza la valoración**: la frase "sin línea activa propia de tratamiento mecánico intensivo" es descriptiva del objeto evaluado (correcto), pero el lector puede interpretarla como anticipación de impactos bajos. En v2.1 el redactor debe separar la descripción técnica (qué tiene y qué no tiene la instalación) de la valoración de lo que eso implica para los impactos.

**A.4.3: la exclusión de R1203 y la contradicción CONT-001**: el piloto manejó esto bien — la tabla de exclusiones declara el resultado, no el proceso de resolución. La nota sobre CONT-001 está en `inferencias_y_gaps.json`. Patrón correcto: Bloque A muestra el estado final; las capas guardan la trazabilidad del proceso.

### L-03: Frases o estilos prohibidos identificados en el piloto

1. **"El DA justifica el encuadre en EIA simplificada exclusivamente por la capacidad de la parcela"** (A.8) — esta frase es correcta como hecho, pero contiene la palabra "justifica" que puede sonar como autojustificación del DA. Mejor: "El encuadre en EIA simplificada se basa en la capacidad de la parcela (art. 7.2.a + Anexo II)".

2. **Referencias a "posible ampliación funcional" y "posible fraccionamiento"** sin más — estas cautelas deben tener su código explícito (CAUTELA-001, CAUTELA-002) para ser trazables.

3. Cualquier formulación del tipo **"los impactos serán limitados porque [descripción técnica]"** dentro del Bloque A.

### L-04: Qué debe blindarse para evitar mezcla entre parcela y conjunto operativo

El riesgo principal del Bloque A no es la elevación de certeza (como en el Bloque B), sino la **expansión silenciosa del alcance**. El redactor, al conocer el contexto completo del expediente, tiene tendencia a incorporar datos del conjunto operativo para completar la descripción.

Los blindajes son:
1. **Regla explícita**: cada capacidad numérica citada en Bloque A es de la parcela, no del conjunto. Si no hay dato específico de la parcela, se declara la vinculación y se referencia el conjunto, sin incorporar sus datos.
2. **Tabla de excluidos obligatoria**: si AG-04 excluyó operaciones, deben estar en la tabla A.4.3. No se puede omitir la tabla porque "no parece relevante".
3. **Autochequeo de expansión**: antes de cerrar el bloque, verificar que ningún dato estructural (capacidad, operación, equipo, superficie) corresponde a las naves vinculadas.
