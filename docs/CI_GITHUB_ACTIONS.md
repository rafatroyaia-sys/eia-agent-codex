# CI-01 — GitHub Actions para validación automática

**Hito**: CI-01  
**Fecha**: 2026-05-31  
**Workflow**: `.github/workflows/ci.yml`  
**Estado**: ACTIVO

---

## Qué hace CI-01

Valida automáticamente el proyecto EIA-Agent v2.1 en cada push y pull request
sobre la rama `master`, ejecutando los siguientes pasos:

| Paso | Descripción |
|------|-------------|
| 1 | Checkout del repositorio |
| 2 | Configurar Python 3.11 |
| 3 | Actualizar pip |
| 4 | Instalar dependencias (`requirements.txt`) |
| 5 | Mostrar versión Python y dependencias clave |
| 6 | Verificar imports del proyecto |
| 7 | Ejecutar suite de tests (`unittest discover -s tests`) |
| 8 | Comprobar archivos prohibidos trackeados |
| 9 | Escaneo de secretos (modo informativo) |

---

## Qué valida CI-01

- **Instalación limpia**: `requirements.txt` instala correctamente en Python 3.11.
- **Imports**: los módulos principales del paquete `eia_agent` se importan sin error.
- **Suite de tests**: todos los tests unitarios pasan sin failures ni errors.
  La suite es completamente offline — sin APIs externas, sin claves, sin DOCX reales.
- **Archivos prohibidos**: el repositorio no contiene tracked `.env`, `venv/`, `tmp/`,
  expedientes piloto, DOCX/PDF/PNG/ZIP generados, ni configuraciones locales.
- **Secretos**: escaneo informativo de patrones de claves en archivos del repositorio.

---

## Qué NO valida CI-01

- No llama a APIs externas (AEMET, WMS, cartografía).
- No valida claves reales ni secrets de GitHub.
- No genera documentos finales pesados (DOCX, PDF, ZIP).
- No ejecuta expedientes piloto reales.
- No declara aptitud administrativa de ningún expediente.
- No conecta a servicios de terceros.
- No ejecuta el pipeline completo de producción.

---

## Cómo ver el workflow en GitHub

1. Ir a: `https://github.com/rafatroyaia-sys/eia-agent/actions`
2. Hacer clic en el workflow **"CI — Validación automática EIA-Agent v2.1"**.
3. Cada ejecución muestra los 9 pasos con sus resultados.

---

## Cómo ejecutarlo manualmente (workflow_dispatch)

1. Ir a: `https://github.com/rafatroyaia-sys/eia-agent/actions`
2. Seleccionar el workflow CI.
3. Hacer clic en **"Run workflow"** → rama `master` → **"Run workflow"**.

---

## Qué hacer si falla

| Paso que falla | Causa probable | Acción |
|----------------|----------------|--------|
| Instalar dependencias | `requirements.txt` roto o paquete incompatible | Revisar `requirements.txt` y probar instalación local |
| Verificar imports | Módulo no encontrado o error de importación | Comprobar que `src/eia_agent/` tiene `__init__.py` y estructura correcta |
| Ejecutar tests | Test nuevo que falla | Ejecutar `python -m unittest discover -s tests` localmente y corregir |
| Archivos prohibidos | Se añadió accidentalmente un archivo prohibido | `git rm --cached <archivo>` y añadir a `.gitignore` |
| Escaneo de secretos | Secreto real detectado (no sintético) | **Revocar el secreto inmediatamente**, limpiar historial git, no hacer push hasta resolverlo |

---

## Por qué secrets-scan es informativo en CI-01

El módulo `secrets-scan` (`config_manager.py`, BE-04) detecta correctamente patrones
de claves API en cualquier archivo. El repositorio contiene archivos de test y
documentación con claves **sintéticas** diseñadas para probar el propio detector
(ver `control_interno/qa_be04_configuracion_segura.md`):

- `tests/test_config_manager.py` — claves sintéticas `sk-test...`, `pk.test...`
- `control_interno/qa_be04_configuracion_segura.md` — secretos de ejemplo documentados
- `docs/AEMET_CLIENT.md` — placeholder `API_KEY_xxxx`

Estos archivos generan **falsos positivos esperados** que hacen que `secrets-scan`
devuelva exit 1. Para no romper la CI por falsos positivos conocidos, el paso 9
tiene `continue-on-error: true` en CI-01.

La salida del escaneo es **visible en el log de CI** para auditoría, pero no
bloquea el workflow.

---

## Qué quedaría para CI-02

| Mejora | Descripción |
|--------|-------------|
| Strict secrets scan | Activar `continue-on-error: false` y añadir allowlist de falsos positivos |
| Matrix OS | Añadir `ubuntu-latest` para validar compatibilidad Linux |
| Artefactos | Guardar resultados de tests y auditoría como GitHub Actions artifacts |
| Protección de rama | Requerir CI verde antes de merge a `master` |
| Cache de dependencias | `actions/cache` para acelerar instalación de pip |
| Cobertura de tests | Añadir `coverage.py` y subir reporte |

---

## Entorno CI

- **OS**: `windows-latest` (Windows Server 2022)
- **Python**: 3.11
- **Trigger**: push a `master`, pull_request a `master`, `workflow_dispatch`
- **Secrets de GitHub usados**: ninguno en CI-01
- **APIs externas**: ninguna
