# Especificación metodológica — AG-10 / Bloque E
## Programa de Vigilancia Ambiental (PVA)

**Versión**: 2.1  
**Estado**: VALIDADO  
**Fecha**: 2026-04-16  
**Baseline**: piloto EIA-2026-RECIMETAL-PARCELA  

---

## §1. Qué es un Bloque E válido en este sistema

El Bloque E es el programa de seguimiento que verifica que las medidas del Bloque D funcionan durante la vida activa de la instalación. No es un catálogo de buenas intenciones — es un sistema operativo con indicadores concretos, umbrales definidos y acciones correctivas previstas.

Un Bloque E válido cumple cinco condiciones:

1. **Trazable hacia D**: cada ficha PVA-XX referencia el IMP-XX que vigila y las medidas M-XX que supervisa. La cadena `IMP-XX → M-XX → PVA-XX` es verificable en ambas direcciones.

2. **Cobertura completa**: todos los impactos negativos de categoría Compatible o superior (antes de medidas) tienen cobertura explícita de seguimiento — ya sea mediante una ficha PVA propia o mediante cobertura explícita en una ficha existente. Los impactos sin cobertura son un GAP-PVA-XXX declarado, no un silencio.

3. **Operativo**: los indicadores son concretos y medibles por el Responsable Ambiental sin equipamiento especializado. Un indicador válido define qué se observa, dónde, con qué frecuencia y qué escala o umbral activa la alarma. Un indicador genérico ("verificar el cumplimiento de las medidas") sin escala ni umbral no es válido.

4. **Prudente en remisión**: la obligación de remitir informes al órgano ambiental queda condicionada a lo que establezca el IIA (art. 47 Ley 21/2013). No se asume remisión periódica automática sin base expresa. El registro interno del PVA está disponible para inspección a requerimiento del órgano, pero eso no equivale a remisión activa.

5. **Transparente sobre pendientes**: el Responsable Ambiental no designado, el órgano ambiental no verificado y la línea base no medida son GAP-PVA-XXX declarados en la sección de gaps del bloque. No se absorben en la narrativa.

---

## §2. Relación exacta entre AG-09, Bloque D y Bloque E

El Bloque E es receptor de dos flujos:

| Origen | Qué aporta al Bloque E |
|--------|------------------------|
| `impactos/pva.json` (AG-09) | Fichas PVA-XX con todos sus campos: indicador, umbral, acción, frecuencia, responsable, registro |
| `impactos/medidas_correctoras.json` (AG-09) | Correspondencia M-XX → IMP-XX que las fichas PVA deben respetar |
| `bloques/D_medidas.md` | Tabla D.4 con columna PVA asociado — confirma qué IMP-XX tienen cobertura PVA y cuáles son GAP |
| `capas/inferencias_y_gaps.json` | GAP-PVA-XXX ya abiertos (Responsable Ambiental, órgano ambiental, línea base) |

**Regla de no-adición**: el Bloque E no diseña nuevas fichas PVA ni nuevos indicadores que no estén en `pva.json`. Si el redactor detecta un IMP sin cobertura PVA en el JSON, lo documenta como GAP-PVA-XXX y no inventa una ficha. La creación de fichas PVA es competencia de AG-09.

**Regla de verificación de cobertura**: antes de redactar E.3, el redactor compara la lista de IMPs de significancia Compatible o superior con la lista de impactos cubiertos en `pva.json`. Los IMPs no cubiertos quedan declarados en E.5.

---

## §3. Cómo redactar cada ficha PVA

### Estructura estándar de ficha (obligatoria)

```
### PVA-XX — [denominación breve]

**Impacto vigilado**: IMP-XX — [denominación del impacto]
**Medidas supervisadas**: M-XX, M-YY

**Indicador**: [descripción concreta de qué se observa, dónde y cómo se registra]
[Si hay escala: tabla de escala de valores]

**Umbral de alarma**: [valor o condición que activa la acción correctiva]

**Acción si se supera el umbral**: [qué se hace exactamente — revisión de qué medida, notificación a quién, en qué plazo]

**Frecuencia**: [periodicidad principal] + [frecuencia adicional si hay desencadenantes]
**Responsable**: [quién ejecuta el seguimiento]
**Registro**: [qué documento se genera, qué debe contener]
**Período**: [durante qué fase o período de la vida del proyecto]
```

Todos los campos son obligatorios salvo "escala de valores", que aplica solo cuando el indicador usa una escala numérica.

### Fichas de impactos positivos

Los impactos positivos (IMP-XX con signo positivo) también tienen ficha PVA si existen en `pva.json`. Su estructura es idéntica salvo que:
- El campo "Umbral de alarma" dice "No aplica — indicador de eficacia positiva"
- El campo "Acción" puede omitirse o simplificarse a "Registro y comunicación al Responsable Ambiental"

### Ficha de revisión anual global

La ficha de revisión anual (PVA-XX — "Revisión interna anual del PVA") es una ficha agregada que verifica el cumplimiento global de todas las medidas y el estado general de todos los indicadores. Es distinta de las fichas de seguimiento individual — no tiene umbral de un indicador concreto; tiene un umbral de cumplimiento global (ej: incumplimiento reiterado sin corrección documentada).

Esta ficha es el soporte del informe anual interno del Responsable Ambiental. La nota sobre remisión al órgano ambiental es obligatoria en esta ficha.

---

## §4. Indicadores: concretos vs genéricos

### Qué hace a un indicador válido

Un indicador es válido cuando permite a cualquier persona con instrucciones básicas determinar, sin ambigüedad, si el umbral se ha superado o no. Los tres elementos mínimos:

1. **Qué se observa**: la variable física, documental o visual que se mide (no "el estado de la medida", sino "la intensidad del depósito de partículas metálicas en el paño")
2. **Dónde**: punto de observación concreto (no "en la parcela", sino "en el perímetro, lado sotavento SO, punto fijo marcado")
3. **Escala o referencia**: cómo se expresa el resultado (índice 0-3, presencia/ausencia, porcentaje de capacidad, cumplimiento sí/no)

### Indicadores genéricos: prohibidos

| Indicador genérico (prohibido) | Por qué no es válido | Alternativa operativa |
|-------------------------------|--------------------|-----------------------|
| "Verificar el cumplimiento de las medidas" | No define qué se verifica ni qué resultado activa la alarma | "Registro de cumplimiento de M-XX con lista de verificación por ítem: cumple/no cumple/parcial" |
| "Control visual del estado ambiental de la parcela" | No define qué factor, qué escala ni qué umbral | "Inspección visual de [suelo / arqueta / perímetro] con registro de [presencia de manchas / estado del paño / nivel de sólidos] usando [escala o descripción]" |
| "Seguimiento de la contaminación" | Demasiado vago — no define parámetro ni método | "Inspección visual del suelo y de la arqueta de retención para detección de manchas de aceite u otros fluidos" |
| "Verificar que no hay impactos" | Circular — el PVA no verifica la ausencia sino controla el umbral | "Registro del índice de [variable] con umbral de alarma en [valor]" |

---

## §5. Calibración de frecuencias

La frecuencia de seguimiento debe ser proporcional al tipo de impacto:

| Tipo de impacto | Frecuencia mínima | Fundamento |
|----------------|------------------|------------|
| Impacto continuo mientras la instalación opera (polvo, ruido) | Semanal o mensual | La presión sobre el factor es constante |
| Impacto discontinuo o episódico (drenaje, lixiviados) | Mensual + tras episodio desencadenante | La presión solo existe en condiciones específicas |
| Impacto de fase / puntual (cese, restauración) | Al inicio o al cierre de la fase | No tiene sentido el seguimiento continuo fuera de esa fase |
| Impacto de gestión (vectores sanitarios) | Trimestral mínimo + actuación urgente si se detecta | La proliferación es gradual pero requiere respuesta rápida |
| Impacto positivo (valorización de residuos) | Anual | Tendencia de largo plazo; sin umbral de alarma |

**Desencadenantes condicionales**: los seguimientos adicionales "tras episodio [X]" son parte del diseño del PVA, no opcionales. Si el JSON de AG-09 los incluye, deben aparecer en la ficha. Si no los incluye pero el tipo de impacto los justifica claramente (ej: lluvia → drenaje), se puede añadir con nota "(incluido por coherencia técnica con el tipo de impacto)".

---

## §6. Responsable Ambiental: tratamiento del gap

El Responsable Ambiental es el ejecutor del PVA. Si no está designado al momento de redactar el Bloque E, es un **GAP-PVA-001 de criticidad ALTA** que aparece en:
- E.2 (estructura del PVA): nota en blockquote declarando el gap y la criticidad
- E.5 (tabla de gaps): fila con código, descripción y criticidad
- D.4 (tabla cierre de Bloque D): si el Bloque D ya está redactado, la columna PVA de las fichas que requieren Responsable Ambiental debe llevar la nota del gap

**Lo que nunca se hace**: no se inventa un nombre o titulación del Responsable Ambiental que no esté en los documentos del promotor. No se presenta el cargo como "a designar por el promotor" como si fuera una formalidad menor — es un requisito operativo de criticidad ALTA.

**Formulación estándar** (de E.2):
```
> ⚠️ **GAP-PVA-001 / GAP-003 activo**: No se ha designado el Responsable Ambiental.
> El PVA no puede ejecutarse sin esta designación.
> Criticidad: ALTA — debe resolverse antes del inicio de la actividad.
```

---

## §7. Remisión al órgano ambiental: la regla crítica

Esta es la frontera jurídica más importante del Bloque E. El PVA es un instrumento de seguimiento interno del promotor. La obligación de remitir informes al órgano ambiental depende de:

1. Lo que establezca el IIA (art. 47 Ley 21/2013) — que en EIA simplificada se llama formalmente "informe de impacto ambiental" y puede contener condiciones específicas de seguimiento
2. La normativa sectorial aplicable (si la actividad es autorización ambiental integrada, licencia de actividad, etc.)
3. Las condiciones que fije el órgano sustantivo en el procedimiento de otorgamiento del permiso

**En ausencia de condición expresa del IIA**, el promotor no tiene obligación automática de remitir informes periódicos al órgano ambiental. Tiene obligación de mantener el registro del PVA disponible para inspección.

**Nota estándar obligatoria** (en E.1 y en la ficha de revisión anual):
> "La obligación y periodicidad de remisión de informes formales al órgano ambiental depende de las condiciones que fije el Informe de Impacto Ambiental (IIA) que resuelva el expediente (art. 47 Ley 21/2013). En ausencia de condición expresa del IIA, no se asume automáticamente la obligación de remitir informes periódicos al órgano ambiental. El registro interno del PVA estará disponible para inspección a solicitud del órgano competente en cualquier momento."

Esta nota no puede suprimirse. No puede reducirse a un paréntesis. Si el redactor considera que la normativa aplicable sí establece remisión obligatoria, debe citarla específicamente y declararlo como CONFIRMADO con la base legal exacta.

---

## §8. Cobertura del PVA: regla de completitud

Antes de considerar el Bloque E listo, el redactor verifica que cada IMP negativo con significancia Compatible o superior (antes de medidas) tiene cobertura explícita de seguimiento.

**Protocolo de verificación de cobertura**:

1. Listar todos los IMPs negativos del `identificacion_valoracion_impactos.json`
2. Para cada IMP: ¿existe una ficha PVA en `pva.json` que lo referencie como `impacto_asociado`?
3. Si no existe ficha propia: ¿está el IMP cubierto de forma explícita por otra ficha (ej: IMP-06 cubierto por PVA-01 para el vector de polvo)?
4. Si la cobertura es implícita: declararlo en la ficha que lo cubre con una nota de cobertura
5. Si el IMP no tiene ninguna cobertura: registrarlo como GAP-PVA-XXX en E.5

**Tratamiento de la cobertura implícita**:
Si una medida reduce dos impactos (ej: M-01 reduce IMP-01 y, de forma indirecta, IMP-06), y el PVA solo tiene ficha para IMP-01, la ficha PVA-01 puede extender explícitamente su cobertura con una nota:
> "Esta ficha también cubre indirectamente el seguimiento de IMP-06 (afección sobre flora/fauna del entorno) a través del control de la dispersión de partículas que constituye el vector de afección principal."

Esto es explicitación de cobertura existente — no creación de una ficha nueva.

---

## §9. Reutilización de registros obligatorios existentes

El sistema debe minimizar las cargas administrativas del promotor sin reducir la calidad del seguimiento. Cuando un registro ya obligatorio por normativa sectorial sirve como fuente de datos del PVA, se declara esta reutilización explícitamente en la ficha PVA.

Ejemplos aplicables:
- RD 553/2020 (Registro de Producción y Gestión de Residuos) → fuente de datos para seguimiento de residuos y trazabilidad de impactos positivos
- Libro de registro de entradas/salidas de vehículos (RD 553/2020) → soporte del PVA de ruido (horario de operaciones)
- Certificados de empresa de control de plagas → soporte del PVA de vectores sanitarios

**Formulación estándar**: "Los datos de [registro obligatorio por normativa XXX] sirven directamente como fuente del PVA-XX sin duplicar cargas administrativas."

---

## §10. Modo test vs expediente real

| Aspecto | Modo test | Expediente real |
|---------|-----------|-----------------|
| Responsable Ambiental | GAP-PVA-001 visible; PVA no ejecutable sin él | Designado y operativo antes del inicio de actividad |
| Línea base de indicadores | Sin medición de referencia; indicadores operativos desde el inicio | Medición de línea base antes del inicio para comparar |
| Indicador PM10 (u otros cuantitativos) | Opcional; declarado como GAP-PVA-003 si el IIA lo condiciona | Implementado si el IIA lo requiere |
| Órgano ambiental destinatario de informes | GAP-PVA-002 (denominación no verificada) | Verificado antes de cualquier remisión |
| Plan de cierre | Mencionado en fichas de fase de cese; detalle básico | Desarrollado con hitos, plazos y verificaciones |
| Fichas de impactos con cobertura implícita | Declaradas con nota de cobertura | Fichas completas o cobertura documentada formalmente |

---

## §11. Estructura mínima obligatoria del Bloque E

```
E.1. Fundamento y alcance del PVA
     — base legal (art. 45 Ley 21/2013, Anexo VI)
     — alcance del PVA (qué cubre, proporcionado a la escala del proyecto)
     — nota estándar sobre remisión al órgano ambiental (OBLIGATORIA)

E.2. Estructura del PVA
     E.2.1. Responsable general (con GAP-PVA-001 si no está designado)
     E.2.2. Registros base (libro/fichero de registro)

E.3. Fichas del PVA
     — una ficha por PVA-XX del pva.json
     — estructura estándar completa (todos los campos)
     — nota de cobertura para IMPs con cobertura implícita

E.4. Calendario del PVA
     — tabla por período (semanal / mensual / trimestral / episodios / anual)
     — incluye desencadenantes condicionales

E.5. Gaps del PVA
     — tabla con ID / descripción / criticidad
     — todos los GAP-PVA-XXX del pva.json
     — IMPs sin cobertura en el PVA declarados aquí
```

No se puede omitir ninguna sección. E.5 puede tener cero filas solo si no hay gaps activos en `pva.json` y todos los IMPs tienen cobertura.

---

## §12a. Reglas incorporadas tras Nave 222 (OBS-M12 — 2026-04-19)

Las siguientes reglas se formalizaron a partir de las observaciones de la auditoría M-12 del expediente NAVE-222. Complementan las especificaciones anteriores.

### E-9 — Fichas PVA condicionadas a resolución de CONTs (IM-07 — OBS-M12-007)

**Problema identificado en Nave 222**: Cuando existe un CONT (contradicción no resuelta), los impactos derivados de él tienen valoración provisional. Los PVA asociados a esos impactos quedan en un estado indefinido — ¿son vigentes? ¿están activos? No había mecanismo explícito para representar este estado.

**Regla**: Si una ficha PVA está condicionada a la confirmación de un CONT, debe presentarse en estado **CONDICIONADO** con referencia explícita al CONT que la activa.

**Formato estándar**:
```
### PVA-XX — [denominación] — ⚠️ CONDICIONADO a resolución de CONT-XXX

**Estado**: CONDICIONADO — se activa si se confirma [X]
**Descripción**: [qué seguimiento se realizaría si se confirma el CONT]
**Condición de activación**: confirmación de CONT-XXX

> Esta ficha PVA no entra en vigor hasta que se resuelva CONT-XXX. Si CONT-XXX 
> se resuelve negativamente (no se confirma), esta ficha queda DESCARTADA.
```

Las fichas CONDICIONADAS se listan en E.3 pero se señalan claramente como no vigentes. En E.5 (gaps), se incluye una fila por cada ficha CONDICIONADA con referencia al CONT.

**Autochequeo E-9**: ¿Hay CONTs abiertos en `inferencias_y_gaps.json` que afecten a impactos con ficha PVA? → Si sí, verificar que las fichas PVA correspondientes tienen estado CONDICIONADO con referencia al CONT.

---

### E-10 — Gap ALTA en impacto positivo es visible en la ficha PVA asociada (RD-07 — OBS-M12-006)

**Problema identificado en Nave 222**: Un impacto positivo cuyo indicador de eficacia depende de un dato con gap ALTA activo tiene un umbral de control provisionalmente incierto. En el expediente, esto no estaba señalizado en la ficha PVA — el umbral se presentaba como definitivo cuando en realidad era provisional.

**Regla**: Si una ficha PVA de un impacto positivo mide indicadores que dependen de un dato afectado por un gap ALTA, la ficha debe incluir una nota de incertidumbre en el umbral de control:

```
> **Nota de incertidumbre**: El umbral de control de este indicador positivo depende de 
> [dato] afectado por GAP-XXX. El umbral es PROVISIONAL hasta resolución de GAP-XXX.
```

Esta nota no suaviza el gap ni lo absorbe. Es una señal explícita para el auditor y para el promotor de que ese umbral necesita ser revisado cuando el gap se resuelva.

**Casos que generan esta nota**:
- PVA de empleo (IMP-09) cuyo umbral de puestos depende de datos del promotor no confirmados
- PVA de valorización (IMP-10) cuyo umbral de toneladas depende de capacidad de proceso no verificada
- PVA de restauración (IMP-11) cuyo umbral de superficie restaurada depende de delimitación de parcela con gap activo

**Autochequeo E-10**: ¿Hay fichas PVA de impactos positivos con umbrales que dependan de datos con gap ALTA activo? → Si sí, añadir nota de incertidumbre en el umbral.

---

## §12. Lecciones del piloto RECIMETAL incorporadas

### Qué funcionó bien y debe protegerse

1. **Nota de remisión al órgano ambiental en E.1 y en PVA-06**: explícita, correcta y en el lugar donde más impacta. Modelo a mantener en todos los expedientes.

2. **GAP-PVA-001 visible y con criticidad ALTA**: el Responsable Ambiental no designado está declarado con su código, su descripción y la consecuencia (el PVA no puede ejecutarse sin él). Correcto.

3. **PVA-01 con indicador operativo concreto**: los paños de tela 20×20 cm con índice 0-3 y puntos fijos barlovento/sotavento son un ejemplo de indicador que cualquier operario puede ejecutar sin equipo especializado. Modelo de buena práctica.

4. **Umbrales concretos en todas las fichas**: PVA-01 (índice ≥2 durante dos semanas consecutivas), PVA-02 (cualquier mancha de fluido), PVA-03 (>50% de capacidad o coloración metálica). Ninguno es vago. Modelo correcto.

5. **Reutilización de RD 553/2020 en PVA-04 y PVA-07**: los registros ya obligatorios por normativa de residuos se emplean como soporte del PVA sin crear carga administrativa nueva. Principio a codificar y reutilizar en futuras instalaciones de gestión de residuos.

6. **Calendario E.4 con desencadenantes condicionales**: "tras episodio de lluvia >5 mm" y "tras episodio de viento >55 km/h" son seguimientos adicionales bien calibrados. No todos los expedientes tendrán los mismos desencadenantes, pero el formato de tabla es el modelo.

7. **PVA-07 para impactos positivos**: incluir el seguimiento de la eficacia positiva (toneladas recicladas por LER) es una buena práctica que distingue este PVA de un mero control de daños. Debe conservarse cuando haya impactos positivos identificados.

### Riesgos detectados (a corregir en siguiente expediente)

1. **IMP-05 e IMP-06 sin cobertura PVA explícita**: los impactos de paisaje (IMP-05) y de flora/fauna (IMP-06) eran Compatible y Compatible residual respectivamente. El PVA del piloto no tiene fichas dedicadas para estos IMPs. PVA-01 cubre IMP-06 de forma implícita (el polvo es el vector de afección sobre flora), pero la cobertura no estaba declarada en la ficha. En el siguiente expediente: declarar la cobertura implícita en la ficha fuente o abrir GAP-PVA-XXX.

2. **"mínimo pero funcional" como calificativo propio en E.1**: aunque el texto añade "proporcionado a la naturaleza y escala del proyecto", el calificativo "mínimo" puede interpretarse como una declaración de insuficiencia. Sustituir por simplemente "proporcionado a la naturaleza y escala del proyecto" sin el "mínimo".

3. **PVA-04 umbral reactivo sin seguimiento proactivo**: el umbral de alarma de PVA-04 (ruido) incluye "queja formal de instalación vecina". Un umbral basado en queja externa es reactivo — el PVA solo detecta el problema cuando ya ha causado un impacto sobre terceros. En expedientes donde IMP-04 sea Compatible (sin medidas) en lugar de Compatible residual, considerar añadir un indicador proactivo.

---

*Especificación redactada en P2 — 2026-04-16*
