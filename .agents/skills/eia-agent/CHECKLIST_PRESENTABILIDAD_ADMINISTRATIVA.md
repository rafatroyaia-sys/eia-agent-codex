# Checklist de presentabilidad administrativa

Aplicar antes de declarar un expediente apto para presentación al órgano ambiental.
**Un solo NO es suficiente para bloquear la presentación.**

---

## BLOQUE 0 — Integridad del expediente

- [ ] La estructura de carpetas está completa (inputs/, capas/, bloques/, impactos/, anejos/, output/)
- [ ] `validate` pasa sin errores de schema
- [ ] `status` no muestra fases BLOCKED ni FAILED
- [ ] No hay archivos corruptos o temporales en inputs/

---

## BLOQUE 1 — Identidad del objeto evaluado (Gate 2)

- [ ] Titular / promotor: nombre oficial verificado — no provisional, no "EMPRESA TEST"
- [ ] Referencia catastral: formato válido (20 chars), verificada en Catastro
- [ ] Coordenadas WGS84 o UTM: presentes y verificadas — no "PENDIENTE", no "ESTIMADO"
- [ ] Modo de trabajo declarado: GABINETE o CAMPO — no NO_DECLARADO
- [ ] Operaciones incluidas declaradas: al menos una operación R/D
- [ ] Operaciones excluidas: declaradas si hay contradicciones abiertas
- [ ] Cero asunciones de test activas (`at_activos = []`)
- [ ] Cero gaps ALTA / CRÍTICA / BLOQUEANTE abiertos relacionados con identidad
- [ ] `evaluate_gate_2(scope, test_mode=False)` → `passed=True`

---

## BLOQUE 2 — Encuadre normativo (Gate 3)

- [ ] Procedimiento determinado (evaluación ordinaria / simplificada / exclusión)
- [ ] Normativa verificada online (no de memoria): BOE y BOC en vigor
- [ ] Órgano ambiental competente identificado
- [ ] Órgano sustantivo identificado
- [ ] Plazo de resolución conocido

---

## BLOQUE 3 — Cartografía (Gate 4)

- [ ] 8 mapas mínimos generados (ubicación, ortofoto, usos, ENP, Natura 2000, inundabilidad, litología, inventario)
- [ ] Fuente oficial identificada para cada mapa
- [ ] `cartografia_trace.json` completo (URL, fecha, escala, CRS por mapa)
- [ ] Ningún mapa marcado como PROVISIONAL sin respaldo de fuente oficial
- [ ] Sistema de referencia correcto (WGS84/EPSG:4326 + REGCAN95/UTM 28N si Canarias)

---

## BLOQUE 4 — Inventario ambiental (Gate 5)

- [ ] 16 factores ambientales con ficha probatoria
- [ ] Cada ficha diferencia dato probado de interpretación
- [ ] No hay "no existe afección/flora/impacto" sin evidencia
- [ ] Semáforo GABINETE/CAMPO declarado por factor
- [ ] Factores CAMPO_NECESARIO: prospección realizada o AT explícita documentada

---

## BLOQUE 5 — Impactos, medidas y PVA (Gate 6)

- [ ] Cadena completa: acción → factor → impacto → valoración → medida → indicador PVA
- [ ] Cero impactos relevantes con estado INDETERMINADO
- [ ] Toda medida tiene tipo correcto (reductora / correctora / compensatoria)
- [ ] No hay medidas PRL presentadas como medidas EIA
- [ ] Afección Natura 2000 evaluada si corresponde (término correcto: "apreciable" no "significativa")
- [ ] Impactos positivos no compensan negativos
- [ ] PVA completo: indicadores, umbrales, responsables, plazos

---

## BLOQUE 6 — Redacción (Gate 7)

- [ ] Bloques A–K completos
- [ ] Todos los gaps ALTA visibles en A.1 o A.3.1 con código explícito
- [ ] No hay texto provisional marcado como definitivo
- [ ] Coherencia interna: lo que está fuera del objeto evaluado, fuera en todos los bloques
- [ ] No hay afirmaciones absolutas sin evidencia ("no existe", "no hay")

---

## BLOQUE 7 — Ensamblaje y auditoría (Gates 8–9)

- [ ] DOCX generado sin errores
- [ ] Portada correcta con datos del promotor y fecha
- [ ] TOC actualizado
- [ ] Anejos completos y referenciados en el texto
- [ ] Auditoría M-12: resultado CONFORME (no CON OBSERVACIONES sin resolución)
- [ ] Checklist art.45 Ley 21/2013 completo

---

## Resultado final

```
APTO PARA PRESENTACIÓN:   todos los bloques con todos los ítems marcados ✅
NO APTO:                  al menos un ítem sin marcar o en duda
```

Registrar fecha y resultado de esta evaluación en `control_interno/`.
