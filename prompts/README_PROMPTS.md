# PROMPTS — EIA-Agent v2.1
## Estructura y convenciones

**Última actualización**: 2026-04-19 (Etapa 1 corta — refactor post-NAVE-222)  
**Estado**: P2 COMPLETADO + ETAPA 1 CORTA COMPLETADA — todos los prompts AG-01 a AG-09, AG-10 (bloques A–K), M-11, M-12 y SYSTEM_BASE VALIDADOS con reglas OBS-M12-001 a OBS-M12-007 incorporadas  
**Nota**: refactor aplicado sobre 9 archivos de prompts + 4 especificaciones en control_interno. Ver `cierre_refactor_prompts_post_nave222.md` para el detalle completo.  

---

## PRINCIPIO DE DISEÑO

Cada agente tiene un system prompt propio, cargado dinámicamente por el orquestador al inicio de la fase correspondiente. Los prompts no se codifican en el código fuente — son archivos de texto versionados y editables sin tocar el código.

Los prompts de redacción (AG-10) son los más extensos y se dividen por bloque del DA para evitar instrucciones contradictorias.

---

## ESTRUCTURA DE CARPETAS

```
/prompts/
├── README_PROMPTS.md           ← este archivo
├── SYSTEM_BASE.md              ← instrucciones comunes a todos los agentes
│
├── AG-01_ingesta.md            ← [VALIDADO] parser + catalogador de documentos del promotor
├── AG-02_extraccion.md         ← [VALIDADO] extractor de entidades estructuradas (HC)
├── AG-03_evidencia.md          ← [VALIDADO] clasificador de estados de evidencia + TR
├── AG-04_cierre_objeto.md      ← [VALIDADO] cierre del objeto evaluado (ficha OB-01)
├── AG-05_triaje_normativo.md   ← [VALIDADO] triaje normativo vivo con verificación BOE/BOC
├── AG-06_cartografia.md        ← [VALIDADO] generación de cartografía WMS con fallbacks
├── AG-07_clima.md              ← [VALIDADO] AEMET + clasificación climática + riesgos naturales
├── AG-08_inventario.md         ← [VALIDADO] fichas probatorias + semáforo evidencia + semáforo campo
├── AG-09_impactos.md           ← [VALIDADO] cadena impactos + Conesa simplificado + medidas + PVA
│
├── AG-10/                      ← redactor, un prompt por bloque
│   ├── README_AG10.md          ← [VALIDADO] principios comunes: no-elevación certeza, dominio propio, qualifiers, gaps, estilo
│   ├── bloque_A_descripcion.md             ← [VALIDADO] subordinado a AG-04, anti-expansión, 8 reglas
│   ├── bloque_B_inventario.md      ← [VALIDADO] traductor AG-08→narrativa, 8 reglas, advertencias F/F/P
│   ├── bloque_C_normativa.md               ← (alias histórico) → ver bloque_C_impactos.md
│   ├── bloque_C_impactos.md               ← [VALIDADO] subordinado a AG-09, 8 reglas, anti-deriva
│   ├── bloque_D_medidas.md                ← [VALIDADO] traductor AG-09→narrativa, 8 reglas, anti-garantismo, trazabilidad D→E
│   ├── bloque_E_pva.md                    ← [VALIDADO] PVA operativo, 8 reglas, cobertura completa, remisión→IIA
│   ├── bloque_F_alternativas.md           ← [VALIDADO] alternativas formales vs reconstruidas, 8 reglas, anti-circular, alternativa 0 ambiental
│   ├── bloque_G_vulnerabilidad.md         ← [VALIDADO] bidireccional, 8 reglas, Seveso+incendio+CC, evidencia limitada
│   ├── bloque_H_natura2000.md             ← [VALIDADO] "afección apreciable", 8 reglas, anti-sobreafirmación
│   ├── bloque_I_conclusiones.md         ← [VALIDADO] cierre técnico del promotor, 8 reglas, anti-deriva conclusiva
│   ├── bloque_J_rnt.md         ← [VALIDADO] RNT: paridad de certeza + anti-OBS-002 + catálogo prohibiciones
│   └── bloque_K_referencias.md            ← [VALIDADO] derivado de JSONs, 8 reglas, estado verificación visible, anti-decorativa
│
├── M-11_ensamblador.md         ← instrucciones de ensamblaje DOCX
└── M-12_auditoria.md           ← [VALIDADO] 9 ejes, 8 reglas, CONFORME/CON OBS/NO CONFORME
```

---

## CONVENCIONES DE CADA PROMPT

### Cabecera obligatoria
```markdown
---
agente: AG-XX
version: 2.1
fase: N
tipo: system | user | tool
estado: VALIDADO | BORRADOR | DEPRECADO
baseline: piloto-recimetal | nuevo
---
```

### Secciones estándar
1. **IDENTIDAD Y ROL**: qué es este agente, qué produce
2. **INPUTS REQUERIDOS**: qué capas JSON y archivos debe tener disponibles
3. **OUTPUTS OBLIGATORIOS**: qué archivos debe escribir, con qué formato
4. **REGLAS NO NEGOCIABLES**: las que no se pueden flexibilizar nunca
5. **INSTRUCCIONES DE EJECUCIÓN**: paso a paso de lo que debe hacer
6. **CRITERIOS DE GATE**: qué condiciones deben cumplirse para que el gate pase

### Herencia de SYSTEM_BASE
Todos los agentes heredan las reglas de `SYSTEM_BASE.md`:
- Reglas 1-6 del CLAUDE.md (evidencia, prudencia, coherencia, etc.)
- Formato de estados de evidencia
- Sistema de coordenadas
- Estructura de la capa JSON que debe escribir

---

## ESTADO ACTUAL DE CADA PROMPT

| Archivo | Estado | Fuente | Notas |
|---------|--------|--------|-------|
| SYSTEM_BASE.md | **VALIDADO** | CLAUDE.md + P2 | v2.1 — 12 secciones, reglas transversales, jerarquía certeza, terminología obligatoria |
| AG-01_ingesta.md | **VALIDADO** | Piloto Recimetal | v2.1, baseline piloto-recimetal |
| AG-02_extraccion.md | **VALIDADO** | Piloto Recimetal | v2.1 — nombre final: extraccion (no entidades) |
| AG-03_evidencia.md | **VALIDADO** | Piloto Recimetal | v2.1, hc_ids obligatorio en TR |
| AG-04_cierre_objeto.md | **VALIDADO** | Piloto Recimetal | v2.1 — nombre final: cierre_objeto (no objeto) |
| AG-05_triaje_normativo.md | **VALIDADO** | Piloto Recimetal | v2.1 — nombre final: triaje_normativo (no normativa) |
| AG-06_cartografia.md | **VALIDADO** | Piloto Recimetal + P2 | v2.1 — catálogo WMS, fallbacks, lecciones piloto |
| AG-07_clima.md | **VALIDADO** | Piloto Recimetal + P2 | v2.1 — AEMET, Köppen, Martonne, riesgos naturales, SVG |
| AG-08_inventario.md | **VALIDADO** | Piloto Recimetal + P2 | v2.1 — 16 fichas, semáforo 6 estados, semáforo campo, afirmaciones prohibidas |
| AG-09_impactos.md | **VALIDADO** | Piloto Recimetal + P2 + Etapa 1 | v2.1 — Conesa todos, efectos acumulativos (AG09-11), cadenas condicionales CONT (AG09-12), diagnóstico≠reducción (AG09-13), PRL separada (AG09-14) |
| AG-10/README_AG10.md | **VALIDADO** | 6 bloques analizados + P2 + Etapa 1 | v2.1 — no-elevación certeza, dominio propio, catálogo frases prohibidas incl. anti-despreciable (RD-05) |
| AG-10/bloque_A_identificacion_y_descripcion.md | **VALIDADO** | Piloto Recimetal + P2 + Etapa 1 | v2.1 — subordinado a AG-04, 10 reglas incl. A-9 (gaps ALTA sobre identidad visibles en A.1/A.3.1) |
| AG-10/bloque_D_medidas.md | **VALIDADO** | Piloto Recimetal + P2 + Etapa 1 | v2.1 — 10 reglas incl. D-9 (diagnóstico≠reductor), D-10 (EIA/PRL separados), cadenas condicionales CONT |
| AG-10/bloque_E_pva.md | **VALIDADO** | Piloto Recimetal + P2 + Etapa 1 | v2.1 — 10 reglas incl. E-9 (PVA CONDICIONADO a CONT), E-10 (gap ALTA en PVA positivo → umbral provisional) |
| AG-10/bloque_B_inventario.md | **VALIDADO** | Piloto Recimetal + P2 | v2.1 — traductor AG-08→narrativa, 8 reglas, advertencias F/F/P |
| AG-10/bloque_C_impactos.md | **VALIDADO** | Piloto Recimetal + P2 + Etapa 1 | v2.1 — 12 reglas incl. C-9 (Conesa todos), C-10 (C.5 acumulativos), C-11 (cadenas condicionales CONT), C-12 (gap ALTA en positivo) |
| AG-10/bloque_F_alternativas.md | **VALIDADO** | Piloto Recimetal + P2 | v2.1 — alternativas formales vs reconstruidas INFERIDO, anti-circular, alternativa 0 ambiental, 8 reglas |
| AG-10/bloque_G_vulnerabilidad.md | **VALIDADO** | Piloto Recimetal + P2 | v2.1 — bidireccional, 8 reglas, Seveso+incendio+CC, declaraciones estándar evidencia limitada |
| AG-10/bloque_H_red_natura_2000.md | **VALIDADO** | Piloto Recimetal + P2 + Etapa 1 | v2.1 — 9 reglas incl. H-9 (anti-despreciable en gabinete), 4 formulaciones prohibidas, 4 alternativas |
| AG-10/bloque_I_conclusiones.md | **VALIDADO** | Piloto Recimetal + P2 | v2.1 — cierre técnico promotor, 8 reglas, anti-deriva conclusiva, promotor≠órgano |
| AG-10/bloque_J_rnt.md | **VALIDADO** | OBS-002 piloto + P2 + Etapa 1 | v2.1 — paridad de certeza, catálogo prohibiciones incl. anti-despreciable (J-3), formulación estándar J.7/J.8 |
| AG-10/bloque_K_referencias.md | **VALIDADO** | Piloto Recimetal + P2 | v2.1 — derivado de JSONs, estado VERIFICADA/REFERENCIADA visible, anti-decorativa, nota metodología |
| M-11_ensamblador.md | **VALIDADO** | Python/python-docx — Nave 222 (2026-04-19) | v2.1 — ensamblar_docx.py, 0 bugs, DOCX 438 KB; pendiente formalizar como prompt explícito (EN-02/EN-05/EN-06 pendientes) |
| M-12_auditoria.md | **VALIDADO** | informe_auditoria_final.md piloto | v2.1 — 9 ejes, 3 calificaciones, anti-OBS-002 en EJE 9 |

---

## PRIORIDAD DE ESCRITURA DE PROMPTS

Los primeros prompts en escribirse (P1) son los que se descubrió en el piloto que tenían impacto en la calidad del output:

1. **SYSTEM_BASE.md** — base para todos
2. **AG-10/bloque_J_rnt.md** — porque J.7 fue demasiado categórico (OBS-002)
3. **AG-10/bloque_H_natura2000.md** — porque requirió microcorrección post-redacción
4. **M-12_auditor.md** — para que la auditoría sea reproducible sin LLM
5. **AG-08_inventario.md** — para incluir el semáforo de campo desde el diseño

---

---

## NOMBRES CANÓNICOS DE ARCHIVOS (P1)

Los nombres definitivos de los prompts AG-01 a AG-05 difieren de los propuestos en el borrador inicial:

| Borrador | Nombre canónico | Razón |
|----------|-----------------|-------|
| AG-02_entidades.md | AG-02_extraccion.md | El agente extrae (HC), no solo nombra entidades |
| AG-04_objeto.md | AG-04_cierre_objeto.md | Refleja la operación de cierre, no solo el objeto |
| AG-05_normativa.md | AG-05_triaje_normativo.md | Refleja la naturaleza de triaje vivo (no inventario) |

---

*Documento actualizado 2026-04-16 — P2 COMPLETADO: AG-01 a AG-09, AG-10 completo (bloques A–K), M-12 y SYSTEM_BASE validados*  
*Actualizado 2026-04-19 — M-11 VALIDADO (Python); Etapa 1 corta completada: 9 prompts + 4 especificaciones actualizadas con reglas OBS-M12-001 a OBS-M12-007; nueva especificación AT system creada*
