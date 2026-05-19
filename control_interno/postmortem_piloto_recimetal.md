# POSTMORTEM — PILOTO EIA-2026-RECIMETAL-PARCELA
## Cierre del expediente piloto y extracción de lecciones aprendidas

**Sistema**: EIA-Agent v2.1  
**Expediente piloto**: EIA-2026-RECIMETAL-PARCELA — RECIMETAL LANZAROTE, S.L.  
**Fecha de cierre del piloto**: 2026-04-13  
**Resultado final de auditoría**: EXPEDIENTE CON OBSERVACIONES EN MODO TEST  
**Fases ejecutadas**: 9 de 9  
**Modo**: TEST — 100% gabinete  

---

## 1. RESUMEN EJECUTIVO DEL PILOTO

El piloto ha producido un Documento Ambiental técnicamente íntegro para una instalación de almacenamiento, clasificación y expedición de residuos metálicos no peligrosos (R1201+R1302, R1203=0) de 1.931,40 m² en el Polígono Industrial de Tenorio, Arrecife, Lanzarote. Se han ejecutado las 9 fases del sistema EIA-Agent v2.1, cerrando con auditoría formal (M-12) y resultado "CON OBSERVACIONES" — sin incoherencias materiales pero con 5 pendientes de criticidad ALTA que requieren trabajo de campo para el expediente real.

**Métricas del piloto:**

| Métrica | Valor |
|---------|-------|
| Días de ejecución (sesiones) | 4 (10, 12, 13 de abril 2026) |
| Fases completadas | 9/9 |
| Documentos input procesados | 5 (2 DOCX procesados, 1 PDF catalogado, 2 MD/DOCX auxiliares) |
| Bloques DA generados | 12 (00_triaje + A-K) |
| Hechos confirmados | 37+ (HC-001 a HC-037) |
| Inferencias y gaps | 20+ (INFERIDOS, PENDIENTES, CAUTELAS) |
| Mapas raster generados | 8 (MAP-001 a MAP-008, WMS automatizado) |
| Archivos climáticos | 4 (JSON, CSV, SVG, MD) |
| Fichas inventario | 16 (FI-01 a FI-16) |
| Impactos valorados | 11 (7 neg + 1 PRL + 3 pos) |
| Medidas propuestas | 10 (M-01 a M-10) |
| Fichas PVA | 7 (PVA-01 a PVA-07) |
| Salidas generadas (SG-) | 35 (SG-001 a SG-035) |
| DOCX final | 1.120 KB (11 bloques + 8 mapas) |
| Errores técnicos recuperados | 3 (WMS, rate-limit AEMET, encoding PS1) |

---

## 2. QUÉ HA FUNCIONADO BIEN

### 2.1. Arquitectura phase/gate

La secuencia de 9 fases con gates de bloqueo ha funcionado correctamente como mecanismo de control. Los gates han evitado que el sistema avanzara con datos incompletos y han forzado la resolución explícita de contradicciones (CONT-001). El modo test ha permitido abrir gates con pendientes documentados, lo que es la alternativa correcta para pilotos.

**Validado para producción**: La estructura de fases y gates se mantiene sin cambios. Es el esqueleto del sistema.

### 2.2. Modelo de 6 capas de datos

Las seis capas JSON (`hechos_confirmados`, `inferencias_y_gaps`, `normativa_aplicable`, `matriz_trazabilidad`, `cartografia_trace`, `salidas_generadas`) han funcionado como base de datos distribuida del expediente. La trazabilidad de HC → TR → bloque → SG ha sido efectiva.

**Punto fuerte**: La `matriz_trazabilidad.json` permite saber exactamente de qué fuente viene cada afirmación del DA. Esto es lo que hace el sistema jurídicamente defendible.

### 2.3. Sistema de estados de evidencia

CONFIRMADO / DECLARADO / INFERIDO / ESTIMADO / PENDIENTE / DESCARTADO. Ha funcionado como mecanismo de control de calidad continuo. La auditoría M-12 no ha encontrado afirmaciones categóricas sin evidencia — el sistema los ha convertido automáticamente en DECLARADO con la cautela correspondiente.

### 2.4. Automatización cartográfica WMS

Los 8 mapas mínimos se han generado mediante llamadas WMS automatizadas. El modelo de resolución de incidencias (IGME 1:1M → alternativa IDECanarias; SNCZI sin cobertura canaria → IDECanarias RIESGOMAP; Natura 2000 IndexOutOfRange → bbox isla completa) ha funcionado bien y está documentado para reutilización.

**Lección**: Los servicios WMS institucionales tienen incidencias frecuentes. El sistema necesita una tabla de fallbacks documentada y verificada periódicamente.

### 2.5. Integración AEMET API

La obtención de normales climatológicas 1981-2010 vía API AEMET OpenData ha funcionado bien (HTTP 200 tras rate-limit resuelto). La identificación de estación más próxima (C029O Lanzarote Aeropuerto, 6,5 km SSO), la clasificación Köppen-Geiger automática (BWh) y el índice de Martonne son procesos directamente reutilizables.

### 2.6. Cadena impactos → medidas → PVA

La cadena completa para los 11 impactos es coherente, trazable y auditada. La metodología Conesa simplificada ha producido resultados proporcionales. Los indicadores del PVA-01 (paños normalizados 20×20 cm) son un resultado original y operativo del piloto.

### 2.7. Regla de prudencia

El sistema ha mantenido con rigor la regla "no afirmar ausencia sin prospección" en todos los factores con nivel de certeza bajo (fauna, flora, patrimonio). Esta es la regla más importante para que el DA sea jurídicamente sostenible.

### 2.8. Distinción promotor / órgano ambiental

Mantenida en todos los bloques donde era relevante (I, E, H, J). Es un requisito no negociable y el piloto lo ha resuelto correctamente.

---

## 3. QUÉ HA FALLADO O QUEDADO DÉBIL

### 3.1. DOCX: dependencia de entorno (ALTA)

**El problema más grave del piloto.** El ensamblaje DOCX requirió un script PowerShell porque no había Python ni Pandoc instalados en el entorno de ejecución. La solución funcionó, pero tiene tres defectos técnicos:

- Referencia huérfana a `numbering.xml` (posible aviso Word).
- Rutas ZIP con barra invertida (problema en entornos no-Windows).
- SVG del climograma no insertable — quedó fuera del DOCX.

**Lección para producción**: El ensamblador M-11 debe ser una pieza Python (python-docx) con entorno controlado. No puede depender del entorno del usuario.

### 3.2. Sin prospección de campo (INHERENTE AL MODO GABINETE)

El inventario ambiental (Fase 5) tiene 6 gaps de inventario, 3 de ellos de criticidad ALTA (fauna, flora, patrimonio). Esto es inherente al modo gabinete, pero en producción el sistema necesita distinguir con mayor nitidez cuándo un DA en modo gabinete es suficiente para la administración y cuándo no.

**Lección**: El sistema debe generar, al cerrar la Fase 5, un `semaforo_campo.md` que clasifique cada factor como GABINETE_SUFICIENTE / CAMPO_RECOMENDADO / CAMPO_NECESARIO, con el criterio jurídico de cada decisión.

### 3.3. Errores 500 / interrupciones de sesión

El contexto de Claude Code se interrumpió varias veces durante la ejecución, requiriendo recuperación manual con instrucciones como "retoma donde lo dejaste". El sistema no tiene checkpoint automático.

**Lección**: Cada fase debe escribir su propio log de estado antes de terminar, de forma que la recuperación sea posible leyendo únicamente `log_orquestador.md` y `README_EXPEDIENTE.md`. Esto ya se ha implementado parcialmente, pero debe ser una regla hard del sistema.

### 3.4. J.7 más categórico que H/I (MENOR)

El resumen no técnico (J.7) afirmó "no afecta" cuando el análisis técnico dice "no se prevé afección apreciable, modo gabinete". Es una inconsistencia de tono menor que la auditoría detectó correctamente, pero que debería ser imposible por diseño.

**Lección**: El redactor AG-10 debe tener un bloque de instrucciones explícito para el resumen no técnico: "El tono del RNT no puede ser más categórico que el bloque técnico correspondiente. Toda afirmación de ausencia de afección en J debe estar cualificada con 'según el análisis realizado' o equivalente."

### 3.5. Bloque 00 en el cuerpo del DA (RESUELTO)

El bloque 00_triaje apareció inicialmente como primera sección del DA en lugar de como apéndice interno. Resuelto en la microcorrección, pero el fallo refleja que el ensamblador M-11 necesita una tabla de bloques-por-posición explícita: qué bloques van al cuerpo del DA, cuáles a anejos, cuáles solo al expediente interno.

### 3.6. IMP-05 e IMP-06 sin PVA propio (MENOR)

Los impactos de paisaje y flora/fauna del entorno no tienen ficha PVA. Proporcionado para una EIA simplificada, pero el sistema debería generar automáticamente un PVA de inspección visual genérico para todos los impactos Compatible o superior que no tengan PVA propio.

### 3.7. Encoding UTF-8 / PowerShell 5.1 (RESUELTO PARA ESTE CASO)

El script PowerShell se codificó inicialmente con em-dashes que cp1252 no podía leer. Resuelto con sustitución de caracteres no-ASCII en el código PS1. La solución es correcta pero frágil: cualquier carácter no-ASCII en una cadena de código PS1 puede romper el script.

**Lección**: El ensamblador de producción no debe depender de PowerShell. Python sin restricciones de encoding es el entorno correcto.

---

## 4. BASELINE TÉCNICO APROBADO

Los siguientes componentes del piloto se consideran **validados como baseline** para el sistema de producción:

### 4.1. Modelo de datos — APROBADO SIN RESERVAS

| Componente | Estado |
|-----------|--------|
| 6 capas JSON (hechos, inferencias, normativa, trazabilidad, cartografía, salidas) | ✅ APROBADO |
| Schema de cada capa (`schemas/eia_schemas_v21.json`) | ✅ APROBADO (requiere formalización) |
| Estados de evidencia (CONFIRMADO/DECLARADO/INFERIDO/ESTIMADO/PENDIENTE/DESCARTADO) | ✅ APROBADO |
| Doble capa de códigos de operaciones (legal_base + operativo_interno) | ✅ APROBADO |
| Doble sistema de coordenadas (WGS84 + REGCAN95 UTM 28N) | ✅ APROBADO |
| Estructura de carpetas del expediente | ✅ APROBADO |

### 4.2. Arquitectura de agentes — APROBADO CON NOTAS

| Agente | Estado |
|--------|--------|
| AG-1 (ingesta) | ✅ APROBADO — parseo DOCX funcional |
| AG-2 (extracción de entidades) | ✅ APROBADO — tabla LER, RC, coords, operaciones |
| AG-3 (evidencia y trazabilidad) | ✅ APROBADO — sistema HC/TR/GAP funcional |
| AG-4 (cierre objeto) | ✅ APROBADO — ficha_objeto_evaluado.md validada |
| AG-5 (triaje normativo) | ✅ APROBADO — consulta online verificada |
| AG-6 (cartógrafo) | ✅ APROBADO CON RESERVA — tabla de fallbacks WMS necesaria |
| AG-7 (clima) | ✅ APROBADO — flujo AEMET API completo |
| AG-8 (inventario) | ✅ APROBADO — 16 fichas, diferencia gabinete/campo |
| AG-9 (impactos/PVA) | ✅ APROBADO — cadena completa, Conesa simplificado |
| AG-10 (redactor) | ✅ APROBADO CON NOTA — J.7 requiere instrucción adicional |
| M-11 (ensamblador) | ⚠️ APROBADO PARCIAL — requiere reescritura en Python |
| M-12 (auditor) | ✅ APROBADO — checklist art.45 + Anexo VI funcional |

### 4.3. Estructura del DA — APROBADA

Los 12 bloques A-K + 00_triaje son la plantilla tipológica para instalaciones de residuos no peligrosos en polígono industrial (tipo R12/R13). Esta estructura, con los estados de evidencia y las advertencias de modo gabinete, es el formato de referencia.

### 4.4. Flujos de datos validados

- Ingesta DOCX → entidades estructuradas → capas JSON ✅
- API AEMET → normales climatológicas → climograma + descripción ✅
- WMS institucionales → PNG descargado → referenciado en inventario ✅
- Capas JSON → bloques markdown → DOCX ensamblado ✅
- DOCX → auditoría M-12 → informe de conformidad ✅

---

## 5. LECCIONES APRENDIDAS PARA LA PRODUCTIZACIÓN

| # | Lección | Impacto en diseño |
|---|---------|------------------|
| L-01 | El modelo de 6 capas JSON es el corazón del sistema — no cambiarlo | Formalizar schemas con validación JSON Schema |
| L-02 | Los gates son imprescindibles — sin ellos el sistema genera incoherencias | Implementar gate-checker automático al inicio de cada fase |
| L-03 | El ensamblador DOCX debe ejecutarse en entorno Python controlado | Reescribir M-11 en python-docx con CI/CD propio |
| L-04 | Los WMS fallan — siempre hay que tener tabla de fallbacks | Crear `config/wms_services.json` con primary + fallback por capa y jurisdicción |
| L-05 | El RNT no puede ser más rotundo que el análisis técnico | Añadir regla explícita en prompt AG-10 para bloque J |
| L-06 | El bloque 00_triaje es un documento interno — no va al DA | Definir tabla de posicionamiento de bloques en M-11 |
| L-07 | La regla de prudencia es la regla más crítica | Añadir validador automático en M-12 para detectar "no existe"/"no hay" sin soporte |
| L-08 | Los checkpoints por fase son imprescindibles para recuperación | Formalizar el log_orquestador como protocolo de checkpoint |
| L-09 | La jurisdicción Canarias tiene particularidades críticas | Crear config/jurisdicciones/canarias.json con WMS, normativa y órganos específicos |
| L-10 | El promotor siempre necesita completar los datos — el sistema no puede inferir todo | Diseñar flujo de solicitud de datos al promotor con prioridad por criticidad |

---

*Documento generado por EIA-Agent v2.1 — Cierre del expediente piloto EIA-2026-RECIMETAL-PARCELA — 2026-04-13*
