# QA-05 — Prueba end-to-end: insercion de figuras reales de NAVE-222

**Fecha:** 2026-05-20
**Hito:** DOC-03 document_figure_inserter.py — validacion con expediente real
**Estado:** COMPLETADO — 6/6 figuras insertadas, 0 warnings, 0 bugs de codigo

---

## 1. Expediente de prueba

**Expediente base:** EIA-2026-RECIMETAL-PARCELA (alias NAVE-222, modo test congelado)
**Copia temporal:** `tmp/qa05_figuras_reales_nave222_20260520_183517`
**Fuente:** copia de `tmp/qa04_document_output_20260520_165211` (resultado de QA-04)
**Figuras reales:** 6 PNGs en directorio `mapas/` del expediente

---

## 2. Figuras detectadas

Directorio de origen: `mapas/` (raiz del expediente)

| ID | Tipo | Archivo | Tamano |
|----|------|---------|--------|
| FIG-001 | MAPA | MAP-001_situacion_general.png | 51 KB |
| FIG-002 | MAPA | MAP-002_emplazamiento.png | 60 KB |
| FIG-003 | MAPA | MAP-003_detalle_parcela.png | 66 KB |
| FIG-004 | MAPA | MAP-004_red_natura_ENP.png | 60 KB |
| FIG-005 | MAPA | MAP-005_usos_suelo_entorno.png | 61 KB |
| FIG-006 | MAPA | MAP-006_riesgo_inundabilidad.png | 68 KB |

---

## 3. Comandos ejecutados

```
# Copia de expediente
xcopy /E /I /Q tmp\qa04_document_output_20260520_165211 tmp\qa05_figuras_reales_nave222_20260520_183517

# Insercion de figuras (write mode)
venv\Scripts\python run_expediente.py tmp\qa05_figuras_reales_nave222_20260520_183517 document-insert-figures --write
```

---

## 4. Resultado de ejecucion

```
Figuras encontradas: 6
Figuras insertadas: 6
Figuras omitidas: 0
Advertencias: 0
DOCX generado: documento_ambiental_borrador_con_figuras.docx
```

---

## 5. Validacion de outputs

### 5.1 Archivos generados

| Archivo | Tamano | Estado |
|---------|--------|--------|
| `documento/documento_ambiental_borrador_con_figuras.docx` | 1715 KB | OK |
| `documento/document_figures_result.json` | 4.3 KB | OK |
| `documento/document_figures_result.md` | 1.6 KB | OK |

### 5.2 DOCX base NO modificado

- `documento/documento_ambiental_borrador.docx`: 1380 KB (igual que en QA-04)
- Sin captions FIG- en DOCX base: VERIFICADO

### 5.3 Contenido del DOCX con figuras (verificado con python-docx)

- Total parrafos: 325
- Heading "Anexo grafico y cartografico": PRESENTE (parrafo 306)
- Figuras insertadas: VERIFICADO

| Caption | Parrafo | Texto |
|---------|---------|-------|
| FIG-001 | 308 | Figura FIG-001. Map 001 situacion general. Tipo: MAPA. Fuente: expediente tecnico. |
| FIG-002 | 311 | Figura FIG-002. Map 002 emplazamiento. Tipo: MAPA. Fuente: expediente tecnico. |
| FIG-003 | 314 | Figura FIG-003. Map 003 detalle parcela. Tipo: MAPA. Fuente: expediente tecnico. |
| FIG-004 | 317 | Figura FIG-004. Map 004 red natura enp. Tipo: MAPA. Fuente: expediente tecnico. |
| FIG-005 | 320 | Figura FIG-005. Map 005 usos suelo entorno. Tipo: MAPA. Fuente: expediente tecnico. |
| FIG-006 | 323 | Figura FIG-006. Map 006 riesgo inundabilidad. Tipo: MAPA. Fuente: expediente tecnico. |

### 5.4 Crecimiento del DOCX

- DOCX base: 1380 KB
- DOCX con figuras: 1715 KB
- Incremento: +335 KB (6 mapas de 51-68 KB cada uno) — coherente

---

## 6. Incidencias detectadas y correcciones

### INCIDENCIA-01 — FIGURE_SOURCE_DIRS no incluia "mapas/"

**Descripcion:** La version inicial de `document_figure_inserter.py` no exploraba
el directorio `mapas/` en la raiz del expediente. NAVE-222 almacena sus mapas en
`mapas/` (no en `cartografia/mapas/` como se asumia).

**Impacto:** Sin la corrección, 0 figuras detectadas → DOCX sin anexo grafico.

**Correccion aplicada:**
- `FIGURE_SOURCE_DIRS` ampliado: añadido `"mapas"` como primera entrada
- Test añadido: `test_finds_png_in_mapas_root` en `test_document_figure_inserter.py`
- Tests post-correccion: 90 OK (antes 89)

---

## 7. Suite de tests

**Comando:** `venv\Scripts\python -m unittest discover -s tests`
**Resultado:** 5842 tests OK, 12 skipped, 0 failures, 0 errors

---

## 8. Conclusion

**Estado:** COMPLETADO

DOC-03 (`document_figure_inserter.py`) funciona correctamente con figuras reales.
El bug de `FIGURE_SOURCE_DIRS` fue detectado, corregido y cubierto con test.
La cadena completa DOC-00 → DOC-01 → DOC-02 → DOC-03 esta validada sobre datos reales.

### Pipeline de documentos — estado final

| Hito | Estado |
|------|--------|
| DOC-00 Manifest | OK |
| DOC-01 Markdown | OK |
| DOC-02 DOCX base | OK |
| QA-04 Cadena MD+DOCX | OK |
| DOC-03 Insercion figuras | OK |
| QA-05 Figuras reales | OK (este informe) |
