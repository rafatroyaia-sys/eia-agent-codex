# QA-BE03 — Prueba real de inicialización de expediente limpio

**Fecha:** 2026-05-29
**Autor:** EIA-Agent v2.1 (sesión QA-BE03)
**Baseline:** Suite 6600 OK, 12 skipped — git status limpio (verificado 2026-05-29)
**Sesión previa cerrada con:** BE-03 COMPLETADO, commit `5dc5191`

---

## 1. Ruta temporal usada

```
tmp/qa_be03_init_expediente_20260529_125430/
├── EIA-2026-TEST-BE03/       ← Pruebas 1, 2, 3, 5
└── EIA-2026-TEST-NO-GUIDES/  ← Prueba 4
```

---

## 2. Verificación inicial

| Check | Resultado |
|-------|-----------|
| `git status --short` | Limpio — sin cambios no confirmados |
| Suite tests baseline | 6600 OK, 12 skipped, 0 failures, 0 errors |
| Rama activa | master |
| Último commit | `5dc5191` BE-03: inicializar estructura estandar de expediente |

---

## 3. Comandos ejecutados

```
# Prueba 1 — normal
python run_expediente.py tmp/qa_be03_init_expediente_20260529_125430/EIA-2026-TEST-BE03 init-expediente

# Prueba 2 — idempotencia
python run_expediente.py tmp/qa_be03_init_expediente_20260529_125430/EIA-2026-TEST-BE03 init-expediente

# Prueba 3 — no borra archivos (tras crear inputs/memoria_tecnica/memoria_prueba.txt con "NO BORRAR")
python run_expediente.py tmp/qa_be03_init_expediente_20260529_125430/EIA-2026-TEST-BE03 init-expediente

# Prueba 4 — --no-guides
python run_expediente.py tmp/qa_be03_init_expediente_20260529_125430/EIA-2026-TEST-NO-GUIDES init-expediente --no-guides

# Prueba 5 — --force (tras modificar README_EXPEDIENTE.md con "MODIFICADO MANUALMENTE")
python run_expediente.py tmp/qa_be03_init_expediente_20260529_125430/EIA-2026-TEST-BE03 init-expediente --force
```

---

## 4. Resultado: inicialización normal (Prueba 1)

**Salida del comando:**
```
Expediente   : EIA-2026-TEST-BE03
Ruta         : ...tmp/qa_be03_init_expediente_20260529_125430/EIA-2026-TEST-BE03
Estado       : CREATED
Carpetas     : 20 creadas, 0 existentes
Archivos     : 6 creados/actualizados, 0 omitidos
  [NOTA] Estructura inicializada para expediente EIA-2026-TEST-BE03.
  [NOTA] Este expediente no declara aptitud administrativa.
```

**Exit code:** 0

---

## 5. Estructura creada

| Carpeta | Resultado |
|---------|-----------|
| inputs/ | OK |
| inputs/memoria_tecnica/ | OK |
| inputs/memoria_explotacion/ | OK |
| inputs/fotos/ | OK |
| inputs/imagenes/ | OK |
| inputs/cartografia_aportada/ | OK |
| control_interno/ | OK |
| fase1/ | OK |
| fase2/ | OK |
| fase3/ | OK |
| fase4/ | OK |
| inventario/ | OK |
| impactos/ | OK |
| auditoria/ | OK |
| documento/ | OK |
| documento/figuras/ | OK |
| cartografia/ | OK |
| cartografia/mapas/ | OK |
| clima/ | OK |
| logs/ | OK |

**Total: 20/20 carpetas creadas.**

| Archivo | Resultado |
|---------|-----------|
| README_EXPEDIENTE.md | OK |
| inputs/INSTRUCCIONES_INPUTS.md | OK |
| control_interno/ESTADO_EXPEDIENTE.md | OK |
| control_interno/PENDIENTES_PROMOTOR.md | OK |
| documento/README_DOCUMENTO.md | OK |
| control_interno/expediente_metadata.json | OK |
| control_interno/init_expediente_result.json | OK |

**Total: 7/7 archivos creados.**

---

## 6. Archivos guía creados — validación de contenido

### README_EXPEDIENTE.md
| Check | Resultado |
|-------|-----------|
| Estructura de carpetas | OK |
| Flujo recomendado / fases | OK |
| Advertencia de alcance | OK |
| No declara aptitud administrativa | OK |

### inputs/INSTRUCCIONES_INPUTS.md
| Check | Resultado |
|-------|-----------|
| Memoria técnica | OK |
| Memoria de explotación | OK |
| Coordenadas | OK |
| Referencia catastral | OK |
| Operaciones | OK |
| Maquinaria | OK |
| Residuos | OK |

### control_interno/ESTADO_EXPEDIENTE.md
| Check | Resultado |
|-------|-----------|
| Checklist inicial (fases/ítems pendiente) | OK |

### control_interno/PENDIENTES_PROMOTOR.md
| Check | Resultado |
|-------|-----------|
| Tabla de pendientes (ALTA/MEDIA/BAJA) | OK |

### documento/README_DOCUMENTO.md
| Check | Resultado |
|-------|-----------|
| Describe outputs documentales (DOCX, ZIP, paquete) | OK |

---

## 7. Validación metadata (expediente_metadata.json)

| Campo | Valor | Resultado |
|-------|-------|-----------|
| expediente_id | EIA-2026-TEST-BE03 | OK |
| tool | EIA-Agent v2.1 | OK |
| status | CREATED | OK |
| administrative_ready | False | OK |
| notes | Incluye advertencia de no aptitud administrativa | OK |
| created_at | 2026-05-29T10:54:50Z (ISO 8601 UTC) | OK |

---

## 8. Validación idempotencia (Prueba 2)

**Salida segunda ejecución:**
```
Estado       : ALREADY_EXISTS
Carpetas     : 0 creadas, 20 existentes
Archivos     : 0 creados/actualizados, 6 omitidos
  [NOTA] El directorio raiz ya existia. Se han respetado los archivos existentes.
```

**Resultado:** OK. No se borró ni sobrescribió nada sin `--force`.
**Exit code:** 0.

---

## 9. Validación no borrado (Prueba 3)

**Archivo de prueba creado:**
```
inputs/memoria_tecnica/memoria_prueba.txt → "NO BORRAR"
```

**Tras re-ejecución sin `--force`:**
- Archivo sigue existiendo: **OK**
- Contenido intacto: `"NO BORRAR"` **OK**
- Estado expediente: `ALREADY_EXISTS`, 0 archivos creados, 6 omitidos: **OK**

---

## 10. Validación --no-guides (Prueba 4)

**Expediente:** EIA-2026-TEST-NO-GUIDES

**Salida:**
```
Estado       : CREATED
Carpetas     : 20 creadas, 0 existentes
Archivos     : 0 creados/actualizados, 0 omitidos
```

**Archivos guía (deben estar ausentes):**
| Archivo | Resultado |
|---------|-----------|
| README_EXPEDIENTE.md | OK (ausente) |
| inputs/INSTRUCCIONES_INPUTS.md | OK (ausente) |
| control_interno/ESTADO_EXPEDIENTE.md | OK (ausente) |
| control_interno/PENDIENTES_PROMOTOR.md | OK (ausente) |
| documento/README_DOCUMENTO.md | OK (ausente) |
| control_interno/expediente_metadata.json | OK (ausente) |

**Exit code:** 0.

---

## 11. Validación --force (Prueba 5)

**Modificación manual previa:**
Se añadió la línea `"MODIFICADO MANUALMENTE"` al final de `README_EXPEDIENTE.md`.

**Salida con `--force`:**
```
Estado       : ALREADY_EXISTS
Carpetas     : 0 creadas, 20 existentes
Archivos     : 6 creados/actualizados, 0 omitidos
```

**Verificación de init_expediente_result.json:**
| Archivo | overwritten |
|---------|-------------|
| README_EXPEDIENTE.md | True |
| inputs/INSTRUCCIONES_INPUTS.md | True |
| control_interno/ESTADO_EXPEDIENTE.md | True |
| control_interno/PENDIENTES_PROMOTOR.md | True |
| documento/README_DOCUMENTO.md | True |
| control_interno/expediente_metadata.json | True |

**README_EXPEDIENTE.md tras `--force`:**
- Contiene "MODIFICADO MANUALMENTE": **NO** (sobrescrito correctamente)
- Contiene estructura estándar: **OK**

**Archivo ajeno inputs/memoria_tecnica/memoria_prueba.txt:**
- Contenido tras `--force`: `"NO BORRAR"` **OK** (no tocado)

**Exit code:** 0.

---

## 12. Incidencias detectadas

**Ninguna.** Todas las pruebas pasaron sin errores de código, comportamiento inesperado ni divergencia entre la especificación y la ejecución real.

---

## 13. Correcciones aplicadas

**Ninguna.** No se detectó ningún bug durante la ejecución.

---

## 14. Resultado suite final

```
Ran 6600 tests in 71.936s
OK (skipped=12)
```

**6600 OK, 12 skipped, 0 failures, 0 errors.**
Idéntico al baseline pre-QA. Ningún test regresionado.

---

## 15. Conclusión

**QA-BE03 COMPLETADO** ✅

Todas las 5 pruebas ejecutadas con resultado OK:

| Prueba | Descripción | Resultado |
|--------|-------------|-----------|
| Prueba 1 | Inicialización normal | OK |
| Prueba 2 | Idempotencia (2ª ejecución) | OK |
| Prueba 3 | No borra archivos existentes | OK |
| Prueba 4 | `--no-guides` (solo carpetas) | OK |
| Prueba 5 | `--force` (sobrescribe guías, respeta ajenos) | OK |

BE-03 puede crear expedientes EIA-Agent limpios desde cero, de forma determinista, idempotente y segura.
