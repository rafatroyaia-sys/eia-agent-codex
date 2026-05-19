# Informe de cierre — Etapa 1 corta: Refactor de prompts post-NAVE-222

**Fecha**: 2026-04-19  
**Expediente de referencia**: EIA-2026-RECIMETAL-NAVE-222  
**Origen**: OBS-M12-001 a OBS-M12-007 (auditoría M-12 NAVE-222)  
**Estado**: **ETAPA 1 CORTA COMPLETADA**

---

## §1. Resumen ejecutivo

Se ha completado el refactor de prompts posterior al expediente piloto NAVE-222. El objetivo era incorporar sistemáticamente las 7 observaciones de la auditoría M-12 (OBS-M12-001 a OBS-M12-007) en los archivos de prompts y especificaciones del sistema EIA-Agent v2.1, de modo que el tercer expediente (P1) no repita los mismos patrones de riesgo.

**Alcance del refactor**: 9 archivos de prompts modificados + 4 especificaciones en `control_interno` actualizadas + 1 especificación nueva creada.

**Observaciones cubiertas**: 7/7 (100% de cobertura).

**Tipo de cambio**: puramente documental — no se ha modificado código, no se han abierto nuevas fases, no se han modificado expedientes cerrados.

---

## §2. Archivos modificados

### 2.1 Prompts del sistema

| Archivo | Reglas añadidas | OBS-M12 cubierta |
|---------|----------------|-----------------|
| `prompts/SYSTEM_BASE.md` | §6 anti-despreciable en terminología; §13 sistema AT completo | OBS-M12-002, OBS-M12-003 (terminología) |
| `prompts/AG-10/README_AG10.md` | Catálogo frases prohibidas: anti-despreciable en gabinete | OBS-M12-003 |
| `prompts/AG-10/bloque_A_identificacion_y_descripcion.md` | Regla A-9: gaps ALTA sobre identidad visibles en A.1/A.3.1; autochequeos 9-10; 2 criterios gate | OBS-M12-001, OBS-M12-005 |
| `prompts/AG-10/bloque_C_impactos.md` | Reglas C-9 (Conesa todos), C-10 (C.5 acumulativos), C-11 (cadenas condicionales CONT), C-12 (gap ALTA en positivo); Paso 5bis; autochequeos 11-14; 4 criterios gate | OBS-M12-003, OBS-M12-004, OBS-M12-006, OBS-M12-007 |
| `prompts/AG-10/bloque_D_medidas.md` | Reglas D-9 (diagnóstico≠reductor), D-10 (EIA/PRL separados); Paso 3bis (cadenas condicionales); autochequeos 9-11; 3 criterios gate | OBS-M12-005, OBS-M12-007 |
| `prompts/AG-10/bloque_E_pva.md` | Reglas E-9 (PVA CONDICIONADO a CONT), E-10 (umbral provisional en positivos con gap ALTA); autochequeos 9-10; 2 criterios gate | OBS-M12-006, OBS-M12-007 |
| `prompts/AG-10/bloque_H_red_natura_2000.md` | Regla H-9: prohibición de "despreciable/nulo/irrelevante" en gabinete; 4 prohibidas, 4 alternativas; autochequeo 9; criterio gate | OBS-M12-003 |
| `prompts/AG-10/bloque_J_rnt.md` | Regla J-3 catálogo: añadida fila anti-despreciable sin medición | OBS-M12-003 |
| `prompts/AG-09_impactos.md` | Reglas AG09-10 (Conesa todos), AG09-11 (efectos acumulativos), AG09-12 (cadenas condicionales), AG09-13 (diagnóstico≠reductor), AG09-14 (PRL separada); autochequeos 9-13 | OBS-M12-003, OBS-M12-004, OBS-M12-005, OBS-M12-007 |

### 2.2 Especificaciones en control_interno

| Archivo | Contenido añadido | OBS-M12 cubierta |
|---------|------------------|-----------------|
| `control_interno/especificacion_bloque_a_identificacion.md` | §8a: origen del problema, tabla de 5 tipos de gap con ubicación obligatoria en Bloque A, autochequeos | OBS-M12-001, OBS-M12-005 |
| `control_interno/especificacion_bloque_c_impactos.md` | §10a: origen de C-9, C-10, C-11, C-12 con narrativa del problema en Nave 222 | OBS-M12-003, OBS-M12-004, OBS-M12-006, OBS-M12-007 |
| `control_interno/especificacion_impactos_ag09.md` | §10a: reglas AG09-10 a AG09-14 con JSON de ejemplo, autochequeos y ejemplos canónicos Nave 222 | OBS-M12-003, OBS-M12-004, OBS-M12-005, OBS-M12-007 |
| `control_interno/especificacion_bloque_d_medidas.md` | §8a: reglas D-9 y D-10 con tabla de tipos, formato PRL, autochequeos, ejemplo canónico | OBS-M12-005, OBS-M12-007 |
| `control_interno/especificacion_bloque_e_pva.md` | §12a: reglas E-9 y E-10 con formatos, casos, autochequeos | OBS-M12-006, OBS-M12-007 |

### 2.3 Archivos nuevos creados

| Archivo | Contenido | OBS-M12 cubierta |
|---------|-----------|-----------------|
| `control_interno/especificacion_asunciones_test.md` | Especificación completa del sistema AT: cuándo activar, qué puede/no puede hacer, formato JSON, propagación a bloques, registro, ejemplo piloto, diferencia AT vs GAP | OBS-M12-002 |

---

## §3. Nuevas reglas por código de observación

### OBS-M12-001 — Gaps ALTA sobre identidad deben ser visibles en Bloque A

**Regla generada**: A-9 (bloque_A, especificacion_bloque_a)

**Formulación**: Los gaps ALTA que afectan a datos de identidad del expediente (titularidad, uso catastral, coordenadas, superficie, título habilitante) deben aparecer en las secciones del Bloque A que los consumen, no solo en las capas internas. El órgano ambiental lee el Bloque A para identificar al promotor y la instalación — si hay un gap sobre esos datos, debe verlo.

**Tabla implementada**:
| Tipo de gap | Ubicación obligatoria en Bloque A |
|-------------|----------------------------------|
| Titularidad / NIF | A.1 |
| Uso catastral discrepante | A.3.1 |
| Discrepancia superficie documentos | A.3.2 |
| Coordenadas no verificadas | A.3.1 |
| Título habilitante inexistente o insuficiente | A.1 y A.8 |

---

### OBS-M12-002 — Sistema AT (Asunciones de Test) formalizado

**Regla generada**: §13 SYSTEM_BASE + especificacion_asunciones_test.md

**Formulación**: Cada AT tiene ID AT-XXX, resuelve exactamente un CONT, tiene estado `ASUMIDO_PROVISIONALMENTE_TEST` (nunca CONFIRMADO), se propaga obligatoriamente a todos los bloques afectados, y activa `impide_aptitud_administrativa: true`. No puede transformar PENDIENTE en CONFIRMADO ni resolver datos de identidad.

---

### OBS-M12-003 — Anti-"despreciable" en modo gabinete

**Reglas generadas**: §6 SYSTEM_BASE, README_AG10, A-9 (implícito), H-9, J-3, AG09-10 (Conesa todos), C-9

**Formulación**: Los términos "despreciable", "nulo", "irrelevante", "insignificante" están prohibidos sin medición o modelización en modo gabinete. Alternativa estándar: "se estima de baja relevancia, sin prospección de campo que lo confirme" o equivalente. La tabla Conesa obligatoria para todos los impactos (incluidos Compatible) garantiza que la baja significancia tiene soporte paramétrico.

---

### OBS-M12-004 — Sección C.5 de efectos acumulativos y sinérgicos

**Reglas generadas**: C-10 (bloque_C), AG09-11 (AG-09), §10a especificacion_bloque_c_impactos

**Formulación**: El art. 45.1.f) Ley 21/2013 exige el análisis de efectos acumulativos y sinérgicos. La sección C.5 es obligatoria con análisis de 4 áreas: acumulación entre impactos del mismo proyecto, sinergia, acumulación con instalaciones del entorno, tendencia temporal. Si no es evaluable, declarar el gap.

---

### OBS-M12-005 — Diagnóstico≠reducción; EIA/PRL separados

**Reglas generadas**: D-9, D-10 (bloque_D y especificacion); AG09-13, AG09-14 (AG-09)

**Formulación**: Las medidas diagnósticas (estudios, mediciones, verificaciones) no pueden justificar reducción de significancia. Las medidas PRL (EPIs, protocolos laborales) no reducen la emisión o inmisión ambiental. Ambas tienen secciones propias en D.3 y no aparecen en la tabla D.4.

**Ejemplo canónico Nave 222**: estudio acústico = diagnóstico (no reduce); insonorización + restricción horaria = correctoras (sí reducen).

---

### OBS-M12-006 — Gap ALTA en impacto positivo visible en C y E

**Reglas generadas**: C-12 (bloque_C), E-10 (bloque_E), §12a especificacion_bloque_e_pva

**Formulación**: Si un impacto positivo tiene un dato clave con gap ALTA activo, la incertidumbre debe ser visible en: (a) la descripción del impacto en Bloque C, con nota de incertidumbre; (b) el umbral de control de la ficha PVA, marcado como PROVISIONAL hasta resolución del gap.

---

### OBS-M12-007 — Cadenas condicionales para CONTs no resueltos (bloques C, D, E)

**Reglas generadas**: C-11 (bloque_C), D (Paso 3bis), E-9 (bloque_E); AG09-12 (AG-09); §10a especificacion_bloque_c_impactos, §8a especificacion_bloque_d_medidas, §12a especificacion_bloque_e_pva

**Formulación**: Un CONT no resuelto genera una cadena condicional que se propaga a los tres bloques de análisis: en C como nota de revisión condicional, en D como medidas PENDIENTES de confirmación, en E como ficha PVA con estado CONDICIONADO. El formato estándar es `⚠️ Cadena condicional — CONT-XXX`.

---

## §4. Cobertura de OBS-M12 — Verificación final

| OBS-M12 | Descripción | Estado |
|---------|-------------|--------|
| OBS-M12-001 | Gaps ALTA sobre identidad visibles en Bloque A | ✅ CUBIERTO — Regla A-9 |
| OBS-M12-002 | Sistema AT formalizado | ✅ CUBIERTO — §13 SYSTEM_BASE + especificación AT |
| OBS-M12-003 | Anti-despreciable en gabinete | ✅ CUBIERTO — §6 SYSTEM_BASE + H-9 + J-3 + C-9 + AG09-10 |
| OBS-M12-004 | C.5 efectos acumulativos obligatoria | ✅ CUBIERTO — C-10 + AG09-11 |
| OBS-M12-005 | Diagnóstico≠reducción; EIA/PRL separados | ✅ CUBIERTO — D-9 + D-10 + AG09-13 + AG09-14 |
| OBS-M12-006 | Gap ALTA en impacto positivo visible | ✅ CUBIERTO — C-12 + E-10 |
| OBS-M12-007 | Cadenas condicionales para CONTs | ✅ CUBIERTO — C-11 + E-9 + Paso 3bis D + AG09-12 |

**Cobertura total**: 7/7 — 100%

---

## §5. Prompts reforzados

Ranking por número de reglas nuevas añadidas:

| Prompt | Reglas nuevas | Observaciones cubiertas |
|--------|--------------|------------------------|
| `AG-09_impactos.md` | 5 reglas (AG09-10 a AG09-14) | OBS-M12-003, 004, 005, 007 |
| `bloque_C_impactos.md` | 4 reglas (C-9 a C-12) | OBS-M12-003, 004, 006, 007 |
| `bloque_D_medidas.md` | 2 reglas + Paso 3bis (D-9, D-10) | OBS-M12-005, 007 |
| `bloque_E_pva.md` | 2 reglas (E-9, E-10) | OBS-M12-006, 007 |
| `SYSTEM_BASE.md` | §6 terminología + §13 AT | OBS-M12-002, 003 |
| `bloque_A_identificacion_y_descripcion.md` | 1 regla (A-9) | OBS-M12-001, 005 |
| `bloque_H_red_natura_2000.md` | 1 regla (H-9) | OBS-M12-003 |
| `bloque_J_rnt.md` | Expansión J-3 catálogo | OBS-M12-003 |
| `README_AG10.md` | Expansión catálogo frases prohibidas | OBS-M12-003 |

---

## §6. Riesgos residuales y pendientes

### Riesgos que quedan abiertos tras Etapa 1

| Riesgo | Descripción | Acción requerida |
|--------|-------------|-----------------|
| RR-01 | Reglas AG09-11 y C-10 (efectos acumulativos) exigen datos del entorno que pueden no estar disponibles en gabinete puro | En P1, testear con un expediente que tenga instalaciones vecinas identificadas. Si no hay datos, documentar el gap como protocolo estándar. |
| RR-02 | El sistema AT (§13 SYSTEM_BASE) tiene lógica compleja de propagación. En el primer expediente que lo use puede haber errores de aplicación | Monitorear en el primer expediente real. Si hay drift, añadir ejemplos concretos. |
| RR-03 | La separación EIA/PRL (D-9, D-10, AG09-13, AG09-14) requiere que el promotor distinga claramente sus medidas — algo que no siempre hace | Añadir en el prompt de AG-03 (evidencia) o AG-09 instrucciones para clasificar medidas del promotor antes de crear `medidas_correctoras.json`. Pendiente de Etapa 2. |
| RR-04 | Los bloques F, G, I, K no se han actualizado con reglas OBS-M12. Aunque no tienen observaciones directas, la regla anti-despreciable no está en sus autochequeos propios | Pendiente revisión en Etapa 2 o en el próximo expediente si aparece el problema. |

### Pendientes fuera del alcance de Etapa 1

- NL-01 (instalador macOS/Windows con CLI Python), NL-05 (orquestador Python), NL-02 (schemas JSON formales): pendientes de P1 código
- EN-02 (prompt explícito M-11 como .md), EN-05 (mapeado campos JSON-DOCX), EN-06 (índice automático): pendientes de P1 ensamblador
- Área 13 (instrumentos normativos nuevos): pendiente de P1
- Área 14 (ítems OB-04, OB-05, RD-05 a RD-09, IM-06, IM-07): **COMPLETADOS en Etapa 1**

---

## §7. Declaración de cierre

**ETAPA 1 CORTA COMPLETADA**

Fecha de cierre: 2026-04-19  
Archivos modificados: 14 (9 prompts + 4 especificaciones + 1 nueva especificación + 1 README_PROMPTS)  
Observaciones cubiertas: 7/7 (OBS-M12-001 a OBS-M12-007)  
Ítems de backlog Área 14 completados: 9/9 (OB-04, OB-05, RD-05, RD-06, IM-06, IM-07, RD-07, RD-08, RD-09)

La base de prompts EIA-Agent v2.1 está lista para ejecutar el tercer expediente (P1) con las reglas de Nave 222 incorporadas.

**Siguiente hito recomendado**: iniciar P1 código con NL-01 (instalador multiplataforma) + NL-05 (orquestador Python básico), según recomendación del postmortem comparativo.

---

*Informe redactado en sesión P2 — 2026-04-19*
