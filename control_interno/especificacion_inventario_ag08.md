# Especificación técnica AG-08 — Inventario ambiental probatorio
## EIA-Agent v2.1 — Productización P2

**Versión**: 1.0  
**Fecha**: 2026-04-15  
**Estado**: VALIDADO — baseline piloto-recimetal + mejoras P2  
**Aplicabilidad**: todos los expedientes EIA en Canarias

---

## 1. Resumen ejecutivo

AG-08 es el agente de inventario ambiental del sistema. Su misión es construir fichas probatorias por factor ambiental, distinguir rigurosamente entre dato verificado, dato inferido y dato ausente, integrar los productos de AG-06 y AG-07, y dejar una base trazable y honesta para AG-09 (impactos) y AG-10 (redacción).

AG-08 no redacta el Bloque B del DA — eso es AG-10. AG-08 construye las fichas de las que AG-10 extrae la información. La calidad del Bloque B depende directamente de la calidad de las fichas: si una ficha oculta una limitación, el bloque la oculta también. Si una ficha declara lo que no sabe, el bloque lo declara también.

El piloto RECIMETAL validó el flujo de 16 fichas en modo gabinete. Esta especificación formaliza ese flujo, corrige el sistema de estados inconsistente del piloto, introduce el semáforo de campo como output obligatorio, y establece qué afirmaciones están prohibidas sin evidencia suficiente.

---

## 2. Qué es una ficha probatoria válida

Una ficha es probatoriamente válida si cumple todas estas condiciones:

1. **Identifica la fuente exacta** del dato que afirma: nombre del servicio, URL, fecha de consulta, escala o periodo.
2. **Declara el estado de evidencia** del dato usando el semáforo de 6 estados (ver §4).
3. **Documenta las limitaciones** de la fuente: escala insuficiente, cobertura parcial, datos desactualizados, ausencia de campo.
4. **No afirma ausencias sin evidencia suficiente**: la frase "no existe X" requiere prospección de campo o fuente con cobertura total del área. En gabinete siempre se usa: "no se detecta en las fuentes consultadas", "no consta en los registros analizados".
5. **Tiene una conclusión operativa** para AG-09: qué sabe el sistema, con qué certeza, y qué limitaciones debe trasladar a la valoración de impactos.
6. **Registra el `semaforo_campo`**: si el factor necesita trabajo de campo para que el DA sea presentable ante la administración.

Una ficha que afirma "no hay fauna protegida" sin prospección de campo no es una ficha probatoria válida. Es una ficha de riesgo.

---

## 3. Estructura mínima de cada ficha

### 3.1 Esquema JSON por ficha

```json
{
  "id": "FI-NN",
  "factor": "nombre del factor ambiental",
  "subfactor": null,
  "estado_evidencia": "CONFIRMADO_CAMPO | CONFIRMADO_GABINETE | INFERIDO_TECNICO | LIMITADO_ESCALA | PENDIENTE_VERIFICACION | NO_CONSTA",
  "modo_obtencion": "gabinete | campo | mixto",
  "dato_principal": {
    "descripcion": "resumen del dato más relevante para EIA",
    "valores_clave": {}
  },
  "fuentes": [
    {
      "tipo": "primaria | secundaria | referencia",
      "nombre": "nombre oficial del servicio o documento",
      "url_o_referencia": "URL o referencia bibliográfica",
      "fecha_consulta": "AAAA-MM-DD",
      "escala_o_periodo": "1:NN o periodo temporal",
      "cobertura_adecuada": true,
      "nota_limitacion": "si la escala/cobertura no es adecuada, explicar por qué"
    }
  ],
  "mapa_asociado": "mapas/MAP-NNN_nombre.png | null",
  "semaforo_campo": "GABINETE_SUFICIENTE | CAMPO_RECOMENDADO | CAMPO_NECESARIO",
  "relevancia_proyecto": "cómo afecta este factor al análisis de impactos y medidas",
  "afirmaciones_prohibidas_sin_campo": [
    "lista de frases que NO pueden usarse sin prospección o fuente específica"
  ],
  "limitaciones": "texto libre sobre limitaciones del dato obtenido",
  "gaps_asociados": ["GAP-INV-NNN"],
  "listo_para_ag09": true,
  "observaciones_expediente_real": "qué debe hacerse diferente en un expediente real"
}
```

### 3.2 Campo `listo_para_ag09`

Valor `true` si el factor tiene suficiente información para que AG-09 valore el impacto (aunque sea con incertidumbre documentada).  
Valor `false` si la ausencia de dato es tal que AG-09 no puede valorar el impacto sin inventar — en ese caso AG-09 registra el impacto como INDETERMINADO hasta que se cierre el GAP.

---

## 4. Semáforo de evidencia — 6 estados

### 4.1 Definición de los estados

| Estado | Color | Definición |
|--------|-------|-----------|
| `CONFIRMADO_CAMPO` | Verde intenso | Dato obtenido de prospección de campo, muestreo, medición in situ o consulta directa al organismo competente con respuesta formal. El hecho está acreditado con visita, muestra o certificación. |
| `CONFIRMADO_GABINETE` | Verde | Dato obtenido de fuente oficial verificada online, con escala y cobertura adecuadas para la magnitud del proyecto. Sin ambigüedad sobre la aplicabilidad al emplazamiento. |
| `INFERIDO_TECNICO` | Amarillo | Dato inferido por razonamiento técnico documentado desde fuentes verificadas. La inferencia es coherente y técnicamente justificable, pero no hay medición directa ni fuente específica del emplazamiento. |
| `LIMITADO_ESCALA` | Naranja claro | Dato disponible pero la escala o cobertura de la fuente consultada es insuficiente para el nivel de detalle requerido. La información existe pero no es específica del emplazamiento concreto. |
| `PENDIENTE_VERIFICACION` | Naranja | Fuente identificada y disponible pero no consultada en el proceso actual. El dato es recuperable sin trabajo de campo. |
| `NO_CONSTA` | Rojo | No existe fuente disponible en gabinete para este factor en el emplazamiento. NO equivale a ausencia del elemento en el terreno. Se desconoce, no se ha descartado. |

### 4.2 Reglas de asignación

- Un factor con una fuente consultada pero de escala inadecuada es `LIMITADO_ESCALA`, no `CONFIRMADO_GABINETE`.
- Un factor inferido de ortofoto sin fuente específica es `INFERIDO_TECNICO`, no `CONFIRMADO_GABINETE`.
- Un factor donde la fuente existe pero no fue consultada es `PENDIENTE_VERIFICACION`, no `NO_CONSTA`.
- `NO_CONSTA` se reserva para factores donde no existe fuente adecuada accesible en gabinete.
- `CONFIRMADO_CAMPO` requiere acreditación de la visita o muestra — no se asigna nunca por inferencia.

### 4.3 Propagación al Bloque B

AG-10 debe trasladar el estado de evidencia al texto del Bloque B. La formulación estándar:

| Estado | Formulación en Bloque B |
|--------|------------------------|
| CONFIRMADO_CAMPO | "Según la prospección de campo realizada..." |
| CONFIRMADO_GABINETE | "Según la cartografía/datos oficiales consultados..." |
| INFERIDO_TECNICO | "De acuerdo con el contexto territorial y las fuentes secundarias analizadas, se infiere que..." |
| LIMITADO_ESCALA | "La información disponible a escala [NNN] indica... si bien esta escala es insuficiente para caracterizar el emplazamiento con detalle." |
| PENDIENTE_VERIFICACION | "No ha sido posible consultar [fuente] en esta fase; el análisis se basa en [fuente alternativa]. Se recomienda su consulta antes del cierre del expediente." |
| NO_CONSTA | "No consta en las fuentes documentales consultadas información específica sobre [factor] en el emplazamiento. Esta ausencia de registro no acredita la inexistencia del elemento." |

---

## 5. Semáforo de campo — 3 niveles por factor

El semáforo de campo es independiente del semáforo de evidencia. Responde a la pregunta: **¿es el dato de gabinete suficiente para que el DA sea técnicamente defendible ante la administración?**

| Nivel | Definición | Consecuencias |
|-------|-----------|---------------|
| `GABINETE_SUFICIENTE` | Para el tipo de proyecto y el nivel de afección esperado, los datos de gabinete son suficientes para la EIA simplificada. La administración no puede exigir campo adicional de forma razonada. | El factor puede cerrarse. |
| `CAMPO_RECOMENDADO` | Los datos de gabinete son suficientes para avanzar pero la calidad del análisis mejoraría significativamente con trabajo de campo. La administración podría solicitarlo en el trámite. | El factor queda con nota de mejora. |
| `CAMPO_NECESARIO` | Los datos de gabinete no son suficientes para que el DA sea sólido ante la administración. El factor tiene relevancia ambiental alta y la ausencia de campo crea vulnerabilidad jurídica o técnica. | El factor genera GAP de criticidad ALTA o MEDIA. |

### 5.1 Criterios de asignación por tipo de factor

| Factor | Criterio de campo mínimo para `GABINETE_SUFICIENTE` |
|--------|------------------------------------------------------|
| Clima | Siempre GABINETE_SUFICIENTE si AEMET con estación a ≤ 25 km |
| Geología | GABINETE_SUFICIENTE si no hay excavaciones; CAMPO_RECOMENDADO si hay movimientos de tierra |
| Suelos | GABINETE_SUFICIENTE si suelo artificializado; CAMPO_NECESARIO si hay suelo natural con riesgo de contaminación |
| Hidrología | GABINETE_SUFICIENTE si no hay cursos permanentes; CAMPO_RECOMENDADO si hay barrancos activos |
| Inundabilidad | CAMPO_RECOMENDADO siempre; CAMPO_NECESARIO si MAP-006 muestra riesgo |
| Calidad del aire | CAMPO_RECOMENDADO si hay emisiones difusas relevantes; CAMPO_NECESARIO si hay receptores sensibles < 200 m |
| Flora | `CAMPO_NECESARIO` si hay suelo no pavimentado en el área de actuación o entorno de 100 m |
| Fauna | `CAMPO_NECESARIO` siempre para fauna protegida; CAMPO_RECOMENDADO para fauna sinantrópica |
| ENP | GABINETE_SUFICIENTE si la distancia > 5 km según cartografía WMS oficial |
| Natura 2000 | GABINETE_SUFICIENTE si la distancia > 5 km con cuantificación GIS o estimación conservadora |
| Paisaje | CAMPO_RECOMENDADO; GABINETE_SUFICIENTE en polígonos industriales de calidad intrínseca baja |
| Patrimonio | `CAMPO_NECESARIO` si hay movimientos de tierra; CAMPO_RECOMENDADO si el suelo tiene actividad arqueológica potencial |
| Socioeconomía | GABINETE_SUFICIENTE para la escala de EIA simplificada |
| Ruido | CAMPO_RECOMENDADO si hay receptores sensibles < 300 m; CAMPO_NECESARIO si la actividad tiene fuentes relevantes |
| Cambio climático | GABINETE_SUFICIENTE para EIA simplificada |
| Riesgos naturales | GABINETE_SUFICIENTE si hay cartografía RIESGOMAP + PGRI; CAMPO_RECOMENDADO si riesgo > BAJO |

### 5.2 Output: semaforo_campo.md

Al cerrar Fase 5, AG-08 genera obligatoriamente `fichas_inventario/semaforo_campo.md` con:
- Tabla de los 16 factores con su nivel de semáforo.
- Lista de factores CAMPO_NECESARIO con el GAP-INV asociado.
- Número de factores CAMPO_NECESARIO — si > 3 en un DA simplificado, añadir nota de riesgo.

---

## 6. Factores ambientales mínimos obligatorios — 16 factores

| ID | Factor | Estado mínimo aceptable en test | Estado para expediente real |
|----|--------|--------------------------------|----------------------------|
| FI-01 | Clima | CONFIRMADO_GABINETE (AEMET) | CONFIRMADO_GABINETE |
| FI-02 | Geología y litología | LIMITADO_ESCALA aceptable si no hay excavaciones | CONFIRMADO_GABINETE con carta a escala adecuada |
| FI-03 | Suelos | INFERIDO_TECNICO aceptable en suelo industrializado | CONFIRMADO_GABINETE si hay riesgo de contaminación |
| FI-04 | Hidrología y drenaje | PENDIENTE_VERIFICACION aceptable | CONFIRMADO_GABINETE con PGRI consultado |
| FI-05 | Inundabilidad | PENDIENTE_VERIFICACION aceptable | CONFIRMADO_GABINETE con PGRI + RIESGOMAP |
| FI-06 | Calidad del aire | INFERIDO_TECNICO aceptable en test | CONFIRMADO_GABINETE con red de vigilancia |
| FI-07 | Flora y vegetación | INFERIDO_TECNICO + GAP ALTA en test | CONFIRMADO_CAMPO en suelo no pavimentado |
| FI-08 | Fauna | NO_CONSTA + GAP ALTA en test | CONFIRMADO_CAMPO para fauna protegida |
| FI-09 | ENP | CONFIRMADO_GABINETE (WMS MITECO) | CONFIRMADO_GABINETE |
| FI-10 | Red Natura 2000 | CONFIRMADO_GABINETE (WMS MITECO) | CONFIRMADO_GABINETE + distancias GIS |
| FI-11 | Paisaje | INFERIDO_TECNICO aceptable en polígono industrial | CONFIRMADO_GABINETE + análisis cuencas visuales |
| FI-12 | Patrimonio cultural | NO_CONSTA en test (acceso limitado) | CONFIRMADO_GABINETE con consulta SIPHA/Cabildo |
| FI-13 | Socioeconomía y usos del suelo | INFERIDO_TECNICO aceptable | CONFIRMADO_GABINETE |
| FI-14 | Ruido y receptores acústicos | INFERIDO_TECNICO aceptable en test | CONFIRMADO_GABINETE si hay receptores sensibles |
| FI-15 | Cambio climático | INFERIDO_TECNICO / normativo | CONFIRMADO_GABINETE |
| FI-16 | Riesgos naturales — síntesis | CONFIRMADO_GABINETE (integra FI-01 + MAP-006) | CONFIRMADO_GABINETE |

---

## 7. Inventario de gabinete vs inventario de campo

### 7.1 Definición operativa

| Concepto | Definición | Impacto en el DA |
|----------|-----------|-----------------|
| **Modo gabinete** | El inventario se construye exclusivamente a partir de fuentes secundarias: cartografía, datos API, normativa, bibliografía, visores online. No hay visita al terreno, toma de muestras ni mediciones in situ. | El DA debe incluir la declaración global de modo gabinete y la nota de prudencia en cada factor con CAMPO_NECESARIO. |
| **Modo campo** | El inventario incluye datos obtenidos de prospección de campo, transectos, muestreos, mediciones acústicas o análisis de laboratorio. Requiere que el promotor encargue los trabajos o los aporte como input. | Los datos de campo tienen estado CONFIRMADO_CAMPO y eliminan el GAP del factor correspondiente. |
| **Modo mixto** | Algunos factores con campo, otros en gabinete. Es el escenario más habitual en expedientes reales. | Cada ficha declara su modo de forma independiente. |

### 7.2 Declaración de modo en el expediente

AG-08 debe incluir en `inventario_ambiental.json`, campo raíz `modo_inventario`:
```json
"modo_inventario": {
  "global": "gabinete | mixto",
  "declaracion": "Texto de advertencia global",
  "factores_con_campo": ["FI-NNN"],
  "factores_exclusivamente_gabinete": ["FI-NNN"]
}
```

---

## 8. Afirmaciones prohibidas sin evidencia suficiente

Las siguientes afirmaciones están prohibidas en las fichas (y en el Bloque B) sin la evidencia especificada:

| Afirmación | Requiere | Formulación alternativa correcta |
|-----------|---------|----------------------------------|
| "No existe flora protegida en el área" | Prospección botánica de campo | "No se detecta flora protegida en las fuentes consultadas; la ortofoto no muestra cubierta vegetal significativa, pero no sustituye a la prospección botánica." |
| "El área carece de vegetación de interés" | Prospección de campo o catálogo botánico con cobertura del emplazamiento | "No se aprecia cubierta vegetal en la ortofoto disponible; sin prospección de campo no puede descartarse la presencia de elementos botánicos de interés en márgenes o zonas no visibles en la imagen." |
| "No existe fauna protegida" | Prospección de campo + consulta al Banco de Datos de Biodiversidad | "No se dispone de datos de fauna protegida específicos del emplazamiento; sin prospección de campo y consulta a los registros oficiales, no puede afirmarse ni descartarse su presencia." |
| "No hay patrimonio arqueológico" | Consulta al SIPHA / Cabildo / Gobierno de Canarias + reconocimiento de campo | "No se ha consultado el registro patrimonial oficial; no puede afirmarse ni descartarse la presencia de elementos patrimoniales." |
| "El suelo es impermeable" | Plano de planta confirmado + informe geotécnico | "La ortofoto muestra una zona industrializada que sugiere impermeabilización; el estado exacto de la solera no ha sido verificado documentalmente." |
| "No existe riesgo de inundación" | PGRI consultado + RIESGOMAP con cobertura adecuada + ausencia en T500 | "El mapa MAP-006 no muestra riesgo significativo en el área para las coberturas consultadas; el PGRI no ha sido analizado en detalle." |
| "El proyecto no afecta a ningún espacio protegido" | Cuantificación GIS con geometrías oficiales, no solo visual cartográfica | "Según la cartografía WMS consultada, el emplazamiento no se superpone con ningún espacio protegido; la distancia al más próximo se estima en > X km (no cuantificada con GIS de precisión)." |
| "No se generarán impactos sobre la calidad del aire" | Modelización de dispersión o datos de red de vigilancia próxima | "Sin datos de la red de vigilancia de calidad del aire y sin modelización de dispersión, no puede cuantificarse el impacto; el análisis es cualitativo." |

> **Regla de oro**: la prueba de que una ficha no tiene afirmaciones prohibidas es que puede defenderse ante el órgano ambiental si este pide la fuente de cada dato. Si la respuesta a "¿de dónde sale este dato?" es "lo inferí del contexto", la ficha es INFERIDA_TECNICA, no CONFIRMADA.

---

## 9. Cómo registrar la ausencia de información

Cuando no existe fuente disponible para un factor:

1. El campo `estado_evidencia` toma el valor `NO_CONSTA` o `PENDIENTE_VERIFICACION` según corresponda.
2. El campo `dato_principal.descripcion` debe ser: "No consta información específica sobre [factor] en el emplazamiento en las fuentes documentales consultadas en gabinete."
3. El campo `fuentes` puede estar vacío o contener las fuentes **intentadas** con el resultado de la consulta.
4. El campo `limitaciones` documenta por qué no hay dato.
5. El campo `semaforo_campo` se asigna en función del criterio de la tabla §5.1.
6. Se crea un `GAP-INV-NNN` en `inferencias_y_gaps.json` con la fuente que debe consultarse.

**No se rellena el dato con razonamiento especulativo**. No se dice "probablemente no haya arqueología porque es un polígono industrial". Se dice "no consta en el registro documental consultado".

---

## 10. Relación con AG-06, AG-07, AG-09 y AG-10

### AG-06 → AG-08 (inputs)

AG-08 utiliza todos los mapas de AG-06 como fuentes secundarias de evidencia:
- MAP-001, MAP-002, MAP-003 → FI-03, FI-07, FI-08, FI-11, FI-13, FI-14
- MAP-004 → FI-10
- MAP-005 → FI-09
- MAP-006 → FI-04, FI-05, FI-16
- MAP-007 → FI-02
- MAP-008 → FI-03, FI-11, FI-13

AG-08 debe comprobar que los mapas existen en `mapas/` antes de referenciarlos como fuente. Si un mapa está en estado PROVISIONAL (sin marcador) o PENDIENTE, registrarlo en la ficha con el estado correspondiente.

### AG-07 → AG-08 (inputs)

AG-08 utiliza directamente los outputs de AG-07:
- `clima/datos_climaticos.json` → FI-01 (clima, viento, temperatura, precipitación)
- Bloque de riesgos naturales de AG-07 → FI-16 (síntesis de riesgos)

FI-01 puede ser CONFIRMADO_GABINETE directamente si AG-07 cerró con estado CONFIRMADO. No hay que volver a consultar AEMET.

### AG-08 → AG-09 (outputs)

AG-09 necesita de cada ficha:
- Estado de evidencia del factor (para modular la certeza de la valoración de impactos).
- `relevancia_proyecto` (para identificar qué impactos analizar).
- `semaforo_campo` (para escalar la criticidad de los impactos si el inventario es débil).
- `listo_para_ag09` (si false, AG-09 registra el impacto como INDETERMINADO).

**Regla**: AG-09 no puede valorar un impacto como COMPATIBLE o MODERADO si la ficha del factor afectado tiene `listo_para_ag09: false`. En ese caso el impacto queda como INDETERMINADO hasta que se cierre el GAP.

### AG-08 → AG-10 (outputs)

AG-10 extrae el contenido del Bloque B directamente de las fichas. Las instrucciones clave:
- El estado de evidencia de la ficha determina la formulación del párrafo (ver tabla §4.3).
- Las `afirmaciones_prohibidas_sin_campo` de la ficha son afirmaciones prohibidas en el Bloque B.
- Las `limitaciones` de la ficha aparecen en el Bloque B como nota explícita.
- AG-10 no puede elevar el nivel de certeza: si la ficha es INFERIDO_TECNICO, el Bloque B no puede decir "se confirma que".

---

## 11. Lecciones del piloto RECIMETAL incorporadas

### 11.1 Qué funcionó bien

1. **Estructura de 16 factores**: cubre todos los aspectos exigidos por el Anexo VI de la Ley 21/2013. No sobra ninguno para una instalación de residuos.
2. **Advertencia global de modo gabinete**: fue el mecanismo más efectivo del piloto. Aplicada en el JSON raíz, en el resumen_inventario.md y en el Bloque B. Debe mantenerse en los tres sitios.
3. **Campo `observaciones_expediente_real`**: en cada ficha, indica qué debe hacerse diferente. Es el mecanismo que convierte el modo test en un borrador útil para el expediente real.
4. **Identificación de GAPs por factor**: la tabla de `gaps_del_inventario` en el resumen fue directamente accionable. El formato se mantiene y formaliza.
5. **FI-09 y FI-10 bien resueltas**: la confirmación de que el proyecto está fuera de ENP y Natura 2000 fue técnicamente sólida, con mapa asociado y distancia estimada conservadora.
6. **FI-01 directamente reutilizable de AG-07**: el traspaso de datos climáticos a la ficha fue limpio. Este patrón se formaliza.

### 11.2 Qué quedó débil o falló

1. **Sistema de estados inconsistente**: el piloto usó CONFIRMADO, ESTIMADO, INFERIDO, LIMITADO, MUY LIMITADO, PENDIENTE — sin criterios de asignación claros. LIMITADO y MUY LIMITADO son la misma categoría con intensidad diferente, lo que no tiene lógica semántica. Corregido con el semáforo de 6 estados de §4.
2. **FI-08 (fauna) casi vacía**: la ficha tenía contenido mínimo. Para el sistema definitivo, una ficha con `NO_CONSTA` tiene que ser igualmente completa en su documentación de la ausencia y sus consecuencias.
3. **FI-12 (patrimonio) sin ningún intento de consulta**: en el piloto no se intentó ni siquiera el SIPHA online. El agente definitivo debe intentar la consulta y registrar el resultado (aunque sea "acceso restringido").
4. **Sin semáforo_campo.md**: el postmortem lo identificó como la lección L-02. Es el output más importante para el promotor: le dice exactamente qué campo necesita y por qué.
5. **Filtración de valoración de impactos hacia las fichas**: el campo `relevancia_proyecto` en algunas fichas del piloto ya empezaba a valorar impactos ("IMP-01, IMP-03"). Aceptable como referencia para AG-09, pero no como valoración. Se mantiene el campo pero con la regla de que es referencia, no valoración.
6. **`nivel_certeza` redundante con `estado_evidencia`**: el piloto tenía ambos campos con contenidos solapados. En el agente definitivo hay un solo semáforo de evidencia (`estado_evidencia`) y el `nivel_certeza` textual se elimina.
7. **Distancias a ENP/RN2000 no cuantificadas**: "estimadas >12 km" y ">15 km" no son suficientes para producción. El agente definitivo debe o bien cuantificarlas con herramienta GIS o bien declarar explícitamente que la cuantificación está pendiente con la estimación conservadora.

### 11.3 Qué queda blindado en el agente definitivo

- Semáforo de 6 estados con criterios de asignación explícitos.
- Semáforo de campo con criterio jurídico/técnico por tipo de factor.
- Lista de afirmaciones prohibidas por factor.
- Output obligatorio `semaforo_campo.md`.
- Regla de que AG-09 no puede valorar si `listo_para_ag09: false`.
- Regla de que AG-10 no puede elevar el nivel de certeza de la ficha.

---

## 12. Diferencias entre modo test y expediente real

| Aspecto | Modo test | Expediente real |
|---------|-----------|-----------------|
| Factores CAMPO_NECESARIO | Permitidos con GAP ALTA documentado; no bloquean gate | Bloquean presentación del DA si el factor tiene relevancia ALTA para el proyecto |
| FI-07 Flora | NO_CONSTA / INFERIDO_TECNICO aceptable | CONFIRMADO_CAMPO o CONFIRMADO_GABINETE (con fuente de cobertura de la zona) |
| FI-08 Fauna | NO_CONSTA aceptable con GAP ALTA | CONFIRMADO_CAMPO para fauna protegida siempre |
| FI-12 Patrimonio | NO_CONSTA aceptable con GAP MEDIA-ALTA | Consulta SIPHA + Cabildo obligatoria; CONFIRMADO_GABINETE mínimo |
| FI-04 Hidrología | PENDIENTE_VERIFICACION aceptable | PGRI analizado en detalle; CONFIRMADO_GABINETE |
| FI-06 Calidad del aire | INFERIDO_TECNICO aceptable | Red de vigilancia consultada para receptores sensibles |
| Distancias ENP/RN2000 | Estimadas conservadoramente aceptable | Cuantificadas con GIS sobre geometrías oficiales |
| semaforo_campo.md | Obligatorio igualmente | Obligatorio; se envía al promotor como lista de trabajos de campo |
| Gate Fase 5 | WARNING si hay CAMPO_NECESARIO | ERROR si hay CAMPO_NECESARIO sin plan de resolución |

---

## 13. Criterios de gate para Fase 5

El gate de Fase 5 pasa si:

| Criterio | Test | Producción |
|----------|------|-----------|
| `fichas_inventario/inventario_ambiental.json` con los 16 factores | OK | OK |
| `fichas_inventario/resumen_inventario.md` generado | OK | OK |
| `fichas_inventario/semaforo_campo.md` generado | OK | OK |
| Todos los estados de evidencia usan el semáforo de 6 estados | OK | OK |
| Ninguna afirmación prohibida en las fichas (validación automática de frases) | OK | OK |
| Fichas FI-07, FI-08, FI-12 con `listo_para_ag09: false` si NO_CONSTA | WARNING | ERROR si impactos relevantes sin ficha |
| `semaforo_campo.md` no tiene > 5 factores CAMPO_NECESARIO sin plan | WARNING | ERROR |
| GAPs de inventario registrados en `inferencias_y_gaps.json` | OK | OK |
| `python tools/run_gate.py <expediente> 5` devuelve exit 0 | OK | OK |

---

*Especificación generada por EIA-Agent v2.1 — Productización P2 — 2026-04-15*
