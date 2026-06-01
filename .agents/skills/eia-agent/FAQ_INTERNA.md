# FAQ interna — EIA-Agent

---

## ¿Cuándo puedo declarar un expediente APTO para presentación?

Solo cuando pasa el `CHECKLIST_PRESENTABILIDAD_ADMINISTRATIVA.md` completo:
validación sin errores, gate 9 --prod APTO, auditoría CONFORME,
sin AT activas, sin gaps ALTA abiertos, cartografía oficial.
Si algún ítem falla, el expediente es NO APTO. No hay grises.

---

## ¿Qué diferencia hay entre DECLARADO y CONFIRMADO?

- **DECLARADO**: dato aportado por el promotor en documentación. Puede ser
  incorrecto, estar desactualizado o no coincidir con registros oficiales.
- **CONFIRMADO**: dato verificado por fuente independiente (Catastro, AEMET,
  Registro oficial, inspección de campo). Solo este estado es administrativamente
  sólido para campos críticos.

Nunca elevar DECLARADO a CONFIRMADO sin verificación real.

---

## ¿Qué es una asunción de test (AT)?

Un dato provisional usado para que el expediente avance en desarrollo o ensayo
cuando el dato real no está disponible. Se registra en `at_activos` del ObjectScope.

Mientras haya AT activas:
- El expediente está en **modo test**.
- No es presentable administrativamente.
- El gate en --prod devuelve ERROR para AT activas.

Para desactivar una AT: obtener el dato real y actualizar el scope eliminando la AT.

---

## ¿Qué hago si falta un documento del promotor que bloquea un gate?

1. Identificar exactamente qué falta y por qué bloquea.
2. Decidir: ¿es ALTA (bloquea avance real) o MEDIA (continúa con AT en test)?
3. Si ALTA: redactar petición con `PLANTILLA_SOLICITUD_PENDIENTES_PROMOTOR.md`.
4. Si MEDIA: activar AT explícita, documentarla en scope.
5. No seguir como si el dato existiera.

---

## ¿Se puede usar "afección significativa" para Natura 2000?

No de forma genérica. La terminología correcta es:
- **"Afección apreciable"**: cuando se detecta potencial afección sin haber
  realizado Evaluación de Impacto en Hábitats (EIHA).
- **"Afección significativa"**: solo tras EIHA específica que lo determine.

Si el expediente no incluye EIHA, usar "afección apreciable" y indicar que
se requiere evaluación adicional si procede.

---

## ¿Los impactos positivos compensan los negativos?

No. Cada impacto negativo relevante tiene valoración y medidas propias.
Un impacto positivo (e.g., mejora de empleo) no reduce la valoración de un
impacto negativo (e.g., afección a flora protegida). Son independientes.

---

## ¿Qué diferencia hay entre medida EIA y medida PRL?

- **Medida EIA**: reduce, corrige o compensa impactos ambientales del proyecto.
  Marco legal: Ley 21/2013 y legislación ambiental autonómica.
- **Medida PRL**: protege a los trabajadores durante la obra o explotación.
  Marco legal: Ley 31/1995 de Prevención de Riesgos Laborales.

Son marcos distintos. No incluir medidas PRL como medidas ambientales del DA.
Pueden coexistir pero no confundirse.

---

## ¿Puedo redactar "no existe impacto" sin prospección de campo?

No. La regla de prudencia prohíbe afirmaciones absolutas de ausencia sin
evidencia. Formular siempre como:
- "No se detecta en las fuentes consultadas."
- "No consta prospección de campo en la zona."
- "Según la documentación analizada, sin datos de campo disponibles."

---

## ¿Qué sistemas de coordenadas usar en Canarias?

- Interoperabilidad y presentación: **WGS84 / EPSG:4326** (grados decimales)
- Medición, control interno y mapas: **REGCAN95 / UTM huso 28N / EPSG:32628**

Guardar siempre ambos sistemas en el ObjectScope y en `cartografia_trace.json`.
No usar ED50 ni proyecciones antiguas.

---

## ¿Qué hago si el status muestra IN_PROGRESS sin avanzar?

```bash
python run_expediente.py <expediente> recover
```

Si el recover detecta inconsistencias, revisar `control_interno/orchestrator_log.json`
para identificar el último evento registrado y retomar desde ahí.
Si el log está corrupto, usar `recover --write-report` y analizar el informe.

---

## ¿Qué módulos Python del motor están disponibles hoy?

| Módulo | Función principal |
|--------|------------------|
| `docx_parser.py` (IN-01) | Parse DOCX → texto + tablas |
| `entity_extractor.py` (IN-02) | Extrae RC, LER, coords, ops, promotor... |
| `evidence_classifier.py` (IN-03) | Clasifica entidades → CandidateFact |
| `input_indexer.py` (IN-05) | Índice de documentos de entrada |
| `object_scope_builder.py` (OB-01) | Construye ObjectScope + ficha MD |
| `object_gate_validator.py` (OB-02) | Valida Gate 2 programáticamente |
| `block_a_gap_visibility.py` (OB-04) | Verifica gaps ALTA en Bloque A |
| `schema_validator.py` (NL-02) | Valida schemas JSON de capas |
| `orchestrator.py` (NL-03) | Gestión de fases y gates |
| `gate_checker.py` (NL-04) | Gate-checker automático |
| `session_recovery.py` (NL-07) | Diagnóstico de sesiones interrumpidas |
| `evidence_state.py` (NL-05) | Estados de evidencia con transiciones |
| `orchestrator_log.py` (NL-06) | Log estructurado de eventos |
| `run_expediente.py` (CLI-01) | CLI: status, validate, gate, recover, log-summary |

No reescribir ni duplicar ninguno de estos módulos.

---

## ¿Qué hago si detecto un bug en el motor durante el trabajo?

1. Anotarlo con descripción precisa (módulo, función, input, comportamiento esperado vs real).
2. Reportarlo en la conversación con el usuario antes de continuar.
3. Si es mínimo y obvio, proponer corrección puntual al usuario.
4. No parchear sin avisar. No silenciar el error.
