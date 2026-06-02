# Referencia formal DOCX - RECIMETAL

Este documento resume criterios de diseno observados en el ejemplo aportado:
`Documento_Ambiental_RECIMETAL_Parcela_v8.docx`.

No es una plantilla juridica ni sustituye la auditoria tecnica. Es una
referencia visual para que el generador DOCX produzca salidas mas cercanas a
un Documento Ambiental administrativo real.

## Rasgos observados

- Documento Word de unas 558 entradas de parrafo y 18 tablas.
- Portada sobria, centrada, con rotulos principales en mayusculas.
- Cuerpo en Calibri Light 12 pt.
- Jerarquia compacta:
  - Titulo 1: 15 pt, negrita.
  - Titulo 2: 13 pt, negrita.
  - Titulo 3: negrita.
  - Titulo 4: negrita cursiva.
- Margenes aproximados:
  - Superior: 2,2 cm.
  - Inferior: 2,0 cm.
  - Izquierdo: 2,5 cm.
  - Derecho: 2,3 cm.
- Indice general amplio antes del cuerpo principal.
- Tablas con cuadricula visible para datos del promotor, normativa,
  operaciones, residuos, impactos, medidas y PVA.

## Adaptacion incorporada

El generador `document_docx_builder` aplica el perfil
`recimetal_admin_reference_v1`:

- Fuente base Calibri Light 12.
- Margenes aproximados a la referencia.
- Portada administrativa centrada.
- Encabezado y pie discretos con expediente y pagina.
- Tablas con estilo `Table Grid`, cabecera sombreada y tamano compacto.
- Nota interna de perfil en `docx_build_result.json`.

## Criterio prudente

La salida no debe rotularse como apta administrativamente por estilo. El estilo
solo mejora presentacion. La aptitud documental depende de cierre de objeto,
evidencia, normativa verificada, cartografia, medidas, PVA y auditoria final.
