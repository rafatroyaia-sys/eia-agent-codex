# Checklist por fases — EIA-Agent v2.1

---

## FASE 1 — Ingesta documental (AG-1 + AG-2 + AG-3)

**Objetivo**: Parsear documentos del promotor, extraer entidades y clasificar evidencias.

**Artefactos mínimos**:
- `inputs/inputs_index.json` — índice de todos los documentos
- Entidades extraídas en formato `ExtractionResult` (IN-02)
- `ClassificationResult` con hechos candidatos (IN-03)
- Sin documentos en estado `ERROR` de parseo

**Bloqueos típicos**:
- Documentos PDF sin parser (estado `PENDIENTE_PARSER_PDF`)
- DOCX corruptos o con contraseña
- Índice incompleto (documentos fuera de inputs/)
- Ninguna entidad extraíble (documento solo con imágenes)

**Comando útil**:
```bash
# No hay comando CLI directo — usar módulos IN-01/IN-02/IN-03 programáticamente
# o revisar inputs_index.json generado
python run_expediente.py <expediente> validate
```

**No avanzar si**: hay documentos sin procesar o índice incompleto.

---

## FASE 2 — Cierre del objeto evaluado (AG-4) ← GATE CRÍTICO

**Objetivo**: Definir exactamente qué se evalúa y qué no.

**Artefactos mínimos**:
- `ficha_objeto_evaluado.md` — ObjectScope completo (OB-01)
- `estado_gate2` = APTO
- Modo declarado (GABINETE o CAMPO)
- Coordenadas en WGS84 y UTM
- RC válida
- Operaciones incluidas y excluidas declaradas

**Bloqueos típicos**:
- Falta titular o RC
- Coordenadas en PENDIENTE
- Modo = NO_DECLARADO
- Contradicciones abiertas (CONT-XXX) sin resolución ni AT
- Discrepancia uso catastral vs declarado sin documentar

**Comando útil**:
```bash
python run_expediente.py <expediente> gate 2
python run_expediente.py <expediente> gate 2 --prod
```

**No avanzar si**: sin coordenadas fiables, RC, operaciones, delimitación y modo declarado.

---

## FASE 3 — Triaje normativo (AG-5)

**Objetivo**: Encuadre legal verificado online.

**Artefactos mínimos**:
- `nota_encuadre_legal.md`
- Procedimiento determinado (ordinaria / simplificada / exclusión)
- Normativa verificada en BOE/BOC en vigor
- Órganos competentes identificados

**Bloqueos típicos**:
- Normativa tomada "de memoria" sin verificar online
- Modificaciones recientes no incorporadas (DL 1/2026, DL 6/2025...)
- Procedimiento incorrecto por tipología del proyecto
- Órgano ambiental incorrecto (estatal vs autonómico)

**Comando útil**:
```bash
python run_expediente.py <expediente> gate 3
```

**No avanzar si**: procedimiento no determinado, normativa sin verificar online, órganos sin identificar.

---

## FASE 4 — Geodatos (AG-6 + AG-7, en paralelo)

**Objetivo**: Cartografía SIG + datos climáticos AEMET.

**Artefactos mínimos**:
- 8 mapas mínimos (MAP-001 a MAP-008)
- `cartografia_trace.json` — trazabilidad por mapa (URL, fecha, escala, CRS)
- Climograma (PNG)
- Datos AEMET: estación más próxima, normales 1981-2010, Köppen-Geiger, Martonne

**Bloqueos típicos**:
- WMS inaccesible (caído o cambiado de URL)
- Mapas con bbox incorrecto
- CRS equivocado para Canarias (usar REGCAN95/UTM 28N)
- Climograma SVG no insertado en DOCX
- Falta trazabilidad de fuente en algún mapa

**Comando útil**:
```bash
python run_expediente.py <expediente> gate 4
```

**No avanzar si**: sin mapas mínimos, trazabilidad incompleta o climograma faltante.

---

## FASE 5 — Inventario ambiental (AG-8)

**Objetivo**: Fichas probatorias por factor ambiental (16 factores estándar).

**Artefactos mínimos**:
- `fichas_inventario/FI-01` a `FI-16`
- Cada ficha: dato → fuente → estado de evidencia → interpretación separada
- Semáforo GABINETE/CAMPO por factor

**Bloqueos típicos**:
- Fichas que dicen "no existe impacto" sin evidencia
- Falta de separación entre dato probado e interpretación
- Factores CAMPO_NECESARIO sin prospección ni AT documentada
- Ausencia de trazabilidad a cartografía

**Comando útil**:
```bash
python run_expediente.py <expediente> gate 5
```

**No avanzar si**: fichas sin evidencia, sin semáforo de campo, sin diferenciación dato/interpretación.

---

## FASE 6 — Impactos, medidas y PVA (AG-9)

**Objetivo**: Cadena completa impacto → medida → indicador PVA.

**Artefactos mínimos**:
- `impactos/matriz_impactos.md`
- Valoración de cada impacto relevante (COMPATIBLE / MODERADO / SEVERO / CRÍTICO)
- Medidas: tipo (reductora / correctora / compensatoria), responsable, plazo
- PVA: indicadores con umbral, responsable, frecuencia, acción si se supera
- Sin impactos en INDETERMINADO

**Bloqueos típicos**:
- Impactos indeterminados sin resolver
- Medidas de PRL presentadas como medidas EIA
- Impactos positivos usados para compensar negativos
- PVA sin indicadores concretos ni umbrales
- Afección Natura 2000 sin evaluación específica

**Comando útil**:
```bash
python run_expediente.py <expediente> gate 6
```

**No avanzar si**: impactos relevantes sin valoración, medidas sin PVA, PVA incompleto.

---

## FASE 7 — Redacción A–K (AG-10)

**Objetivo**: Bloques narrativos coherentes y completos.

**Artefactos mínimos**:
- `bloques/A_identificacion_y_descripcion.md` — gaps ALTA visibles en A.1/A.3.1
- `bloques/B_` a `bloques/K_` — todos los bloques completos
- Coherencia: lo excluido del objeto no aparece en ningún bloque
- Sin afirmaciones absolutas sin evidencia

**Bloqueos típicos**:
- Gaps ALTA de identidad no visibles en A.1/A.3.1 (verificar con OB-04)
- Texto provisional mezclado con texto definitivo
- Incoherencia entre bloques (algo en B que contradice A)
- Uso de "no existe impacto" sin soporte probatorio

**Comando útil**:
```bash
python run_expediente.py <expediente> gate 7
```

**No avanzar si**: hay pendientes críticos abiertos o gaps ALTA sin visibilidad en Bloque A.

---

## FASE 8 — Ensamblaje DOCX (M-11)

**Objetivo**: DOCX profesional con portada, TOC, estilos, mapas y anejos.

**Artefactos mínimos**:
- `output/DA_[expediente].docx`
- Portada con datos correctos
- TOC actualizado
- Mapas insertados como imágenes
- Anejos referenciados en el texto

**Bloqueos típicos**:
- Rutas de imagen erróneas
- SVG no convertido a PNG
- Numbering.xml huérfano en DOCX
- Estilos de párrafo inconsistentes

**Comando útil**: ensamblador Python (`ensamblar_docx.py`).

---

## FASE 9 — Auditoría final (M-12)

**Objetivo**: Checklist art.45 + coherencia + formato → CONFORME.

**Artefactos mínimos**:
- Resultado de auditoría: CONFORME / CON OBSERVACIONES / NO CONFORME
- Listado de observaciones si no es CONFORME
- Ningún pendiente crítico abierto

**Bloqueos típicos**:
- Observaciones no resueltas antes del cierre
- DOCX con errores de formato no detectados antes
- Incoherencia entre anejos y texto principal

**Comando útil**:
```bash
python run_expediente.py <expediente> gate 9
```

**No avanzar (no presentar)**: sin auditoría CONFORME.
