# Especificación metodológica — Bloque J: Resumen No Técnico (RNT)
## EIA-Agent v2.1 — Productización P2

**Versión**: 1.0  
**Fecha**: 2026-04-15  
**Estado**: VALIDADO — baseline OBS-002 piloto-recimetal + P2  
**Aplicabilidad**: todos los expedientes EIA generados por el sistema

---

## 1. Qué es un RNT válido en este sistema

El Resumen No Técnico (RNT) es un documento de síntesis, no un documento de argumento. Su función legal es permitir que personas sin formación técnica ambiental comprendan qué es el proyecto, dónde está, qué impactos puede tener, qué medidas se tomarán y cuál es la conclusión del promotor. Está exigido por el Anexo VI de la Ley 21/2013 como parte integrante del Documento Ambiental.

Un RNT es válido si cumple las siguientes condiciones:

1. **Subordinación**: toda afirmación del RNT tiene su origen en un bloque técnico y no supera su nivel de certeza.
2. **Completitud de lo negativo**: los impactos negativos significativos están mencionados aunque sean Compatibles.
3. **Visibilidad de limitaciones**: el modo gabinete, las lagunas de información y los pendientes relevantes están declarados.
4. **Claridad de rol**: las conclusiones del promotor están presentadas como posición del promotor, no como resolución técnica o administrativa.
5. **Longitud proporcionada**: es una síntesis, no un resumen extendido. Para una EIA simplificada de una instalación industrial de < 5.000 m², el RNT no debe superar las 2.500 palabras.

Un RNT que suena más concluyente que el análisis técnico no es un RNT válido. Es un riesgo jurídico.

---

## 2. Relación con los bloques técnicos: la jerarquía de subordinación

El RNT es el último eslabón de la cadena de certeza, no el primero. La jerarquía es:

```
AG-08 (fichas, estado de evidencia)
    ↓
AG-09 (valoración de impactos, medidas, PVA)
    ↓
AG-10 bloques A-K (redacción técnica con calificadores)
    ↓
AG-10 bloque J (síntesis para no especialistas)
    ↓
El RNT hereda la certeza de los bloques técnicos — nunca la supera
```

Regla de dependencia concreta:

| Sección del RNT | Bloque técnico fuente | Qué hereda obligatoriamente |
|-----------------|----------------------|----------------------------|
| J.1 — Descripción del proyecto | Bloque A | Operaciones incluidas/excluidas, capacidad, RC |
| J.2 — Entorno ambiental | Bloque B | Estado de evidencia de cada factor |
| J.3 — Impactos | Bloque C/E | Significancia con medidas de cada impacto |
| J.4 — Medidas | Bloque D/G | Nombre y función de cada medida |
| J.5 — Vigilancia | Bloque E/PVA | Indicadores y frecuencias del PVA |
| J.6 — Lagunas | Bloque I | GAPs de criticidad ALTA y MEDIA declarados |
| J.7 — Conclusión | Bloques H + I | Nivel de certeza de cada conclusión ambiental |

**Regla de cruce pre-redacción de J.7**: antes de escribir J.7, el redactor debe leer el texto literal de H.4 (conclusión Natura 2000) y de I.4 (valoración global del promotor), e identificar el nivel de certeza usado en cada frase. J.7 no puede usar un nivel de certeza superior al de H.4 o I.4 en ninguna afirmación.

---

## 3. Tono: los tres movimientos tónicos prohibidos

El fallo más común —y el que materializó OBS-002— no es una mentira técnica sino un deslizamiento tónico. Son tres movimientos que el redactor debe identificar y bloquear:

### 3.1 La caída del cualificador

El análisis técnico usa cualificadores de certeza: "se prevé", "no se aprecia", "apreciable", "según el análisis realizado", "en modo gabinete". El RNT tiende a eliminarlos por brevedad.

**Ejemplo del piloto (OBS-002)**:
- Bloque H: *"No se aprecia afección indirecta apreciable... [Estado: INFERIDO]"*
- Bloque I: *"No origina afección directa ni indirecta **apreciable**"*
- J.7 piloto: *"el proyecto **no afecta** de forma directa ni indirecta a ningún espacio Natura 2000"*

El cualificador "apreciable" desapareció. La forma condicional "no se aprecia / no se prevé" se convirtió en presente absoluto "no afecta". El modo gabinete desapareció.

**Regla**: el RNT puede simplificar el lenguaje técnico, pero no puede eliminar los cualificadores de certeza. Si el análisis dice "apreciable", el RNT dice "apreciable". Si dice "según el análisis realizado", el RNT lo dice o lo parafrasea con equivalente.

### 3.2 La elevación de INFERIDO a CONFIRMADO

El estado de evidencia INFERIDO_TECNICO del inventario (AG-08) significa que el dato se construyó por razonamiento, no por medición. El RNT no puede presentarlo como dato verificado.

**Ejemplo del piloto**:
- FI-09/FI-10: `CONFIRMADO_GABINETE` para la no-superposición con ENP/RN2000 (cartografía consultada).
- FI-07 (flora): `INFERIDO_TECNICO` (no hay prospección de campo).
- J.7 piloto: omite la distinción — mezcla CONFIRMADO con INFERIDO en la misma frase de conclusión.

**Regla**: si una conclusión del RNT se basa en factores con estado INFERIDO_TECNICO, LIMITADO_ESCALA o NO_CONSTA, debe incluir el cualificador correspondiente.

### 3.3 La conclusión del promotor como hallazgo técnico

El bloque I siempre introduce las conclusiones con "el promotor concluye que..." o "el promotor considera que...". El RNT tiende a eliminar el sujeto y convertir la posición del promotor en una afirmación técnica sin autor.

**Regla**: las conclusiones de J.7 y J.8 se atribuyen explícitamente al promotor. Nunca se presentan como si fueran el Informe de Impacto Ambiental o la resolución del órgano ambiental.

---

## 4. Catálogo de afirmaciones: prohibidas y permitidas

### 4.1 Afirmaciones prohibidas (con alternativa correcta)

| Afirmación prohibida | Por qué está prohibida | Alternativa correcta |
|---------------------|----------------------|---------------------|
| "El proyecto no afecta a X" | Absoluto sin cualificador; equivale a CONFIRMADO_CAMPO que no existe | "Según el análisis realizado, no se prevé afección apreciable sobre X" |
| "No existe impacto sobre X" | Absoluto; solo permitido si el impacto fue explícitamente descartado en el análisis con estado CONFIRMADO | "No se ha identificado impacto significativo sobre X en el análisis realizado" |
| "No hay fauna protegida" | Requiere prospección de campo (CAMPO_NECESARIO en AG-08) | "El inventario en modo gabinete no ha detectado fauna protegida; sin prospección de campo no puede descartarse su presencia" |
| "No hay flora protegida" | Ídem | Ídem para flora |
| "No hay patrimonio arqueológico" | Requiere consulta SIPHA/Cabildo | "No se han consultado los registros de patrimonio cultural; no puede afirmarse ni descartarse la existencia de elementos patrimoniales" |
| "No existe riesgo de inundación" | Requiere PGRI analizado en detalle | "El mapa de riesgo consultado no muestra riesgo significativo; el análisis detallado del PGRI está pendiente" |
| "El estudio demuestra que..." | "Demuestra" implica prueba absoluta; el análisis está basado en fuentes secundarias | "El análisis indica que..." / "Las fuentes consultadas muestran que..." |
| "Queda descartado el impacto sobre..." | "Descartar" implica evidencia de campo que no existe | "No se prevé, según el análisis realizado, impacto apreciable sobre..." |
| "El proyecto no requerirá EIA ordinaria" | Corresponde determinar al órgano ambiental, no al promotor | "El promotor considera que el proyecto no debería requerir EIA ordinaria; la determinación corresponde al órgano ambiental" |
| "El informe ambiental concluye que..." | El Informe de Impacto Ambiental lo formula el órgano ambiental (art. 47 Ley 21/2013); el promotor presenta el Documento Ambiental | "El Documento Ambiental presentado por el promotor concluye que..." |
| "Totalmente compatible / absolutamente seguro / ningún riesgo" | Superlativos sin evidencia de campo | "Los impactos identificados son de nivel Compatible (el nivel más bajo de la escala)" |
| "Se ha comprobado que no existe X" | "Comprobar" implica verificación directa; en modo gabinete no hay comprobación | "Las fuentes documentales consultadas no muestran X" |
| "Como queda demostrado en el análisis..." | Ídem | "Como se indica en el análisis realizado..." |

### 4.2 Formulaciones seguras y aceptables

Las siguientes formulaciones son seguras porque mantienen el cualificador de certeza:

| Contexto | Fórmula segura |
|---------|---------------|
| Conclusión general (factor sin campo) | "Según el análisis realizado, no se prevé [impacto] apreciable sobre [factor]." |
| Conclusión ENP/Natura (CONFIRMADO_GABINETE + INFERIDO) | "La cartografía oficial no muestra superposición con ningún espacio protegido; a la distancia estimada de X km, no se aprecia vía de afección indirecta según el análisis realizado." |
| Factor sin datos (NO_CONSTA) | "No se ha consultado [fuente]; no puede afirmarse ni descartarse la [presencia / afección]." |
| Impacto valorado como Compatible | "El impacto identificado sobre [factor] es de nivel Compatible, que es el nivel más bajo de la escala de valoración." |
| Posición del promotor | "El promotor considera que el proyecto puede realizarse de forma compatible con el entorno ambiental, aplicando las medidas propuestas." |
| Rol del órgano ambiental | "La determinación sobre si el proyecto puede realizarse o sobre si debe someterse a evaluación ordinaria corresponde en exclusiva al órgano ambiental del Gobierno de Canarias." |
| Modo gabinete | "Este Documento Ambiental ha sido elaborado en modo gabinete, basándose en fuentes documentales y cartografía oficial. No se ha realizado prospección de campo." |
| Gap relevante | "El análisis de [factor] es limitado porque [razón]. Antes de la presentación formal del expediente, el promotor deberá [acción concreta]." |

---

## 5. Tratamiento de temas específicos en el RNT

### 5.1 Pendientes y gaps declarados

J.6 debe listar todos los GAPs de criticidad ALTA del expediente, en lenguaje llano. No se pueden ocultar en notas al pie ni minimizar con eufemismos.

Formato sugerido para J.6:
> "Este Documento Ambiental está elaborado en modo gabinete. Los siguientes aspectos están pendientes de completar antes de la presentación formal del expediente o durante la tramitación:
> - [GAP-NNN] — [descripción en lenguaje llano] — [qué necesita el promotor para resolverlo]
> - ..."

J.7 no puede omitir la existencia de gaps relevantes que afectan a las conclusiones. Si hay un GAP ALTA sobre fauna, J.7 no puede afirmar conclusiones absolutas sobre fauna.

### 5.2 Incertidumbres y modo gabinete

Si el expediente es modo gabinete:
- J.6 declara: "El inventario ambiental ha sido elaborado en modo gabinete. Los factores [lista] requieren reconocimiento de campo para un análisis más preciso."
- J.7 cualifica todas las conclusiones sobre esos factores con "según el análisis realizado en modo gabinete".

No se puede mencionar el modo gabinete solo en J.6 y luego escribir J.7 como si el expediente fuera de campo.

### 5.3 ENP y Natura 2000

Es el punto de mayor riesgo de OBS-002. La formulación de J.7 para ENP/Natura debe:

1. Nombrar los espacios más próximos y su distancia estimada.
2. Usar la misma cualificación que el bloque H: "no se aprecia afección apreciable" si H usó ese lenguaje.
3. Mencionar que las distancias son estimadas en gabinete si no se cuantificaron con GIS.
4. No decir nunca "no afecta" sin el cualificador.

**Formulación estándar para el caso de proyecto fuera de espacios protegidos a >10 km**:
> "Los espacios naturales protegidos y los espacios de la Red Natura 2000 más próximos se encuentran a más de [X] km del proyecto (estimación en modo gabinete). La cartografía oficial no muestra superposición directa. Según el análisis realizado, no se prevé afección apreciable, directa ni indirecta, sobre estos espacios."

### 5.4 Conclusiones del promotor

J.7 y J.8 son las conclusiones del promotor. Deben quedar claras dos cosas:

1. **Quién concluye**: "El promotor considera que..." / "La empresa estima que...". No "el análisis demuestra que".
2. **Quién decide**: "La determinación final sobre si el proyecto puede realizarse, y sobre si requiere evaluación de impacto ordinaria, corresponde en exclusiva al órgano ambiental competente (art. 47 Ley 21/2013)."

La segunda frase es obligatoria en J.7 o J.8.

---

## 6. Longitud y estructura mínima

### 6.1 Estructura mínima

| Sección | Contenido mínimo | Longitud orientativa |
|---------|-----------------|---------------------|
| J.1 | Quién, qué proyecto, dónde, para qué | 1-2 párrafos |
| J.2 | Descripción del entorno en lenguaje llano, con indicación de ENP y Natura próximos | 2-3 párrafos |
| J.3 | Impactos principales: nombre, magnitud, efecto de las medidas | 3-5 párrafos o tabla simple |
| J.4 | Las 3-5 medidas más relevantes explicadas en lenguaje accesible | 1 tabla o lista corta |
| J.5 | PVA: qué se controla, con qué frecuencia, quién | 1 párrafo o lista |
| J.6 | Lagunas y pendientes en lenguaje llano | 1-2 párrafos (obligatorio si hay CAMPO_NECESARIO) |
| J.7 | Conclusión del promotor con cualificadores y reconocimiento del rol del órgano ambiental | 3-5 frases máximo |

### 6.2 Límites de longitud

- Total RNT: 1.500-2.500 palabras para EIA simplificada de instalación única.
- J.7 específicamente: **máximo 5 frases**. No es una recapitulación de todo el expediente. Es la posición final del promotor con sus limitaciones declaradas.
- Si el RNT supera las 2.500 palabras en una EIA simplificada, es probable que esté repitiendo el análisis técnico en lugar de sintetizarlo.

---

## 7. Diferencias entre modo test y expediente real

| Aspecto | Modo test | Expediente real |
|---------|-----------|-----------------|
| Cualificadores en J.7 | Obligatorios; mismo estándar que en producción | Obligatorios |
| Mención del modo gabinete | Obligatoria | Obligatoria (o indicar qué campo se realizó) |
| Gaps en J.6 | Todos los de criticidad ALTA, incluso si no bloquean el gate en test | Todos los de criticidad ALTA y MEDIA |
| Conclusión del órgano ambiental | La frase de reconocimiento del rol del órgano es obligatoria igualmente | Obligatoria |
| Fauna/flora sin campo | J.6 los lista; J.7 no los usa como base de conclusión positiva | Ídem, y son gaps bloqueantes |
| Frases de "modo test" | Pueden incluirse notas internas `[MODO TEST]` | No |

---

## 8. OBS-002 como caso de estudio canónico

### 8.1 Qué falló exactamente

**Bloque H.4.3** (texto técnico, estado INFERIDO):
> "No se aprecia afección indirecta **apreciable** sobre los espacios Natura 2000 por dispersión de partículas metálicas, **según el análisis gabinete realizado**."

**Bloque I.4** (conclusión técnica del promotor):
> "El proyecto **no origina afección directa ni indirecta apreciable** sobre los espacios Naturales Protegidos, los espacios Red Natura 2000 ni los valores naturales singulares de Lanzarote."

**J.7** (lo que salió):
> "El estudio concluye que el proyecto **no afecta de forma directa ni indirecta** a ningún espacio natural protegido ni a ningún espacio Natura 2000."

Tres omisiones en una sola frase:
1. Se eliminó **"apreciable"** → el análisis cualifica con "apreciable"; el RNT lo convirtió en absoluto.
2. Se eliminó **"según el análisis realizado en modo gabinete"** → el análisis es una inferencia técnica, no una verificación; el RNT lo presentó como conclusión firme.
3. Se cambió **"no origina afección apreciable"** (con sujeto epistémico implícito) por **"no afecta"** (presente indicativo absoluto, sin agente).

### 8.2 Consecuencias potenciales

En expediente real, el órgano ambiental puede:
- Objetar que el resumen no técnico afirma de forma absoluta algo que el análisis técnico solo puede inferir en modo gabinete.
- Solicitar aclaraciones o informe complementario sobre la metodología usada para afirmar la ausencia total de afección.
- Reducir la credibilidad del DA por incoherencia entre su cuerpo técnico y su resumen.

### 8.3 Corrección canónica

La formulación correcta para J.7 en el caso RECIMETAL habría sido:
> "Los espacios Natura 2000 de Lanzarote (Malpaís de La Corona, Los Volcanes, Los Ajaches) se encuentran a más de 15 km del proyecto según la cartografía consultada. Según el análisis realizado en modo gabinete, el promotor considera que el proyecto no origina afección apreciable, directa ni indirecta, sobre estos espacios."

Añade: cartografía consultada + distancia estimada + "según el análisis realizado en modo gabinete" + "el promotor considera" + mantiene "apreciable".

---

*Especificación generada por EIA-Agent v2.1 — Productización P2 — 2026-04-15*
