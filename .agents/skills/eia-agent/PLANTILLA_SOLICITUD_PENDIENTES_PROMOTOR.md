# Plantilla: Solicitud de información pendiente al promotor

## Instrucciones de uso

1. Antes de redactar, revisar `inputs_index.json` — no pedir lo que ya está procesado.
2. Revisar `hechos_clave.json` y `inferencias_y_gaps.json` — pedir solo lo que bloquea un gate.
3. Clasificar cada pendiente por criticidad (ALTA = bloquea avance / MEDIA = continúa con AT).
4. Ser concreto: documento, campo, formato, plazo.
5. No pedir aclaraciones que el técnico puede resolver por otras fuentes.

---

## Plantilla de correo / escrito profesional

```
Asunto: Solicitud de información técnica — Expediente EIA-[ID] / [Nombre del proyecto]

Estimado/a [nombre del promotor o representante],

En el marco de la elaboración del Documento Ambiental del expediente
[nombre del proyecto / referencia administrativa], y tras el análisis
inicial de la documentación aportada, necesitamos que nos facilite
la siguiente información antes de continuar con el proceso:

---

DOCUMENTACIÓN PENDIENTE — CRITICIDAD ALTA (bloquea avance)

[Para cada ítem de criticidad ALTA:]

1. [CAMPO: Título del pendiente]
   - Motivo: [por qué se necesita y qué gate bloquea]
   - Formato esperado: [PDF firmado / tabla Excel / coordenadas UTM / ...]
   - Referencia: [campo específico, capítulo del proyecto técnico donde debería constar]
   - Plazo solicitado: [fecha concreta]

---

DOCUMENTACIÓN PENDIENTE — CRITICIDAD MEDIA (permite continuar con condiciones)

[Para cada ítem de criticidad MEDIA:]

2. [CAMPO: Título del pendiente]
   - Motivo: [por qué se necesita]
   - Formato esperado: [...]
   - Plazo solicitado: [fecha concreta]

---

NOTAS ADICIONALES

[Indicar si hay discrepancias o contradicciones que el promotor debe aclarar,
 por ejemplo diferencia entre uso catastral y uso declarado, o entre el
 conjunto operativo declarado y el autorizado administrativamente.]

Sin perjuicio de continuar el trabajo con la documentación disponible,
la falta de los documentos de criticidad ALTA impedirá el cierre del
[objeto evaluado / encuadre normativo / inventario ambiental / ...] hasta
su recepción y revisión.

Quedamos a su disposición para cualquier aclaración.

Atentamente,
[Nombre del técnico]
[Empresa consultora]
[Fecha]
```

---

## Ejemplos de ítem de criticidad ALTA

```
1. Estudio acústico actualizado
   - Motivo: necesario para valorar impacto sonoro en Fase 5 (inventario ambiental)
             y para justificar medidas correctoras en Fase 6.
   - Formato esperado: informe firmado por técnico competente + datos de medición
   - Referencia: art. XX del RD YYY/ZZZZ
   - Plazo solicitado: [fecha]

2. Verificación de referencia catastral 2462302DS4026S0001GQ
   - Motivo: RC declarada en documentación no coincide con uso catastral registrado
             ("almacén agrario" vs "uso industrial declarado"). Bloquea Gate 2.
   - Formato esperado: certificación catastral o nota simple del Catastro
   - Plazo solicitado: [fecha]

3. Coordenadas UTM verificadas de la parcela
   - Motivo: las coordenadas aportadas son aproximadas (declaradas, no verificadas).
             Necesarias para cartografía oficial y límite del objeto evaluado.
   - Formato esperado: coordenadas REGCAN95/UTM huso 28N (si Canarias) en tabla
                       o shapefile
   - Plazo solicitado: [fecha]

4. Autorización administrativa de operaciones R1203 y R1301
   - Motivo: las operaciones están declaradas pero no se aporta resolución autorizatoria.
             Necesaria para confirmar el conjunto operativo real.
   - Formato esperado: copia de la resolución de autorización ambiental integrada o
                       equivalente
   - Plazo solicitado: [fecha]

5. Aclaración sobre conjunto operativo de gestión
   - Motivo: el proyecto técnico menciona operación R1302 en texto libre pero no
             figura en la tabla de operaciones autorizadas. Contradicción CONT-001.
   - Formato esperado: confirmación escrita del conjunto operativo definitivo
   - Plazo solicitado: [fecha]
```

---

## Ejemplos de ítem de criticidad MEDIA

```
1. Certificado IGPC (Informe de Gestión de Proyectos de Canarias), si aplica
2. Informe de patrimonio cultural (prospección arqueológica)
3. Fichas de especies protegidas observadas en la zona de influencia
4. Estudio de filtración de lixiviados (si hay suelos potencialmente contaminados)
5. Plano de detalle de la instalación a escala 1:500 o superior
6. Memoria justificativa de la gestión de residuos generados en la obra
```
