# EIA_SOURCES_CATALOG — Catálogo de fuentes ambientales de referencia

## Qué es este catálogo

`config/reference_sources/eia_sources_catalog.json` es un registro estructurado
de los recursos web y servicios de datos que el equipo técnico usa habitualmente
para la elaboración de Estudios de Impacto Ambiental.

Incluye portales de cartografía, datos climáticos, catastro, espacios protegidos,
geología, ruido, calidad del aire y fuentes autonómicas para Canarias y Andalucía.

---

## Lo que NO implica este catálogo

- **No implica verificación automática online.** Ninguna URL ha sido consultada
  programáticamente para comprobar que está activa. El campo `estado` de todas
  las entradas es `REFERENCIA_MANUAL`.

- **No es un módulo de consulta.** El catálogo es un archivo de referencia estático.
  La lógica de consulta online se implementará en los módulos futuros CA-01 a CA-05
  (cliente WMS) y TN-01 (verificación normativa).

- **No contiene credenciales.** Las API keys (AEMET, Mapbox) se gestionan via
  variables de entorno. Ver `docs/ENVIRONMENT_VARIABLES.md`.

---

## Para qué sirve ahora

1. **Base de conocimiento compartida**: el equipo tiene un único sitio donde
   consultar qué portales usar para cada tipo de análisis.

2. **Mapa de dependencias para el roadmap técnico**: los módulos de cartografía
   (CA-01 a CA-05) usarán este catálogo como fuente de URLs de servicios WMS.

3. **Auditoría de trazabilidad**: cada mapa o dato del inventario ambiental
   podrá referenciar un `id` de este catálogo (SRC-XXX) como fuente de respaldo.

4. **Onboarding técnico**: técnicos nuevos saben inmediatamente a qué portales
   acudir para cada fase del expediente.

---

## Ciclo de vida de una fuente

```
REFERENCIA_MANUAL          →  VERIFICADA_ONLINE
  (estado inicial)              (solo cuando el módulo la consulte realmente)
```

Una fuente pasa a `VERIFICADA_ONLINE` únicamente cuando el módulo Python
correspondiente la consulta exitosamente durante la ejecución de un expediente.
El estado no se actualiza manualmente — lo gestiona el módulo.

---

## Estructura de cada entrada

```json
{
  "id": "SRC-001",
  "nombre": "Nombre descriptivo",
  "categoria": "clima | cartografía base | catastro | inundabilidad | ...",
  "ambito": "estatal | autonómico | local",
  "uso": "Descripción concisa de para qué se usa en el expediente",
  "url": "https://...",
  "fase_relacionada": "Fase N",
  "estado": "REFERENCIA_MANUAL | VERIFICADA_ONLINE",
  "notas": ["Notas opcionales"]
}
```

---

## Categorías incluidas

| Categoría | Entradas | Ámbito |
|-----------|----------|--------|
| clima | SRC-001, SRC-002 | Estatal |
| cartografía base | SRC-003, SRC-004, SRC-005 | Estatal |
| catastro | SRC-006, SRC-007 | Estatal |
| inundabilidad | SRC-008, SRC-009, SRC-010 | Estatal |
| hidrología | SRC-011 | Estatal |
| Red Natura 2000 / ENP | SRC-012 a SRC-017 | Estatal |
| calidad del aire | SRC-018 | Estatal |
| ruido | SRC-019, SRC-020, SRC-021 | Estatal |
| geología | SRC-022, SRC-023, SRC-024 | Estatal |
| usos del suelo / SIGPAC | SRC-025, SRC-026 | Estatal |
| Andalucía / REDIAM | SRC-027, SRC-028, SRC-029 | Autonómico |
| Canarias / Grafcan | SRC-030 | Autonómico |

**Total: 30 fuentes.** Extraídas del documento "SITIOS WEB IMPORTANTES Y RELEVANTES
PARA LA EIA" aportado por el equipo.

---

## Relación con módulos del roadmap

| Módulo | IDs que usará |
|--------|--------------|
| CA-01 (`wms_services.json`) | SRC-003, SRC-005, SRC-006, SRC-008, SRC-013, SRC-022, SRC-030 |
| CA-02 (cliente WMS) | SRC-003, SRC-005, SRC-006, SRC-008, SRC-013, SRC-022, SRC-030 |
| CA-05 (`canarias.json`) | SRC-030 |
| CL-01 (AEMETClient) | SRC-002 |
| TN-01 (consulta normativa) | Pendiente — no en este catálogo (BOE/BOC) |
| IV-01 (fichas inventario) | SRC-018, SRC-019, SRC-022, SRC-025 |

---

## Cómo añadir nuevas fuentes

1. Editar `config/reference_sources/eia_sources_catalog.json`.
2. Asignar el siguiente ID correlativo (SRC-031, SRC-032...).
3. Estado inicial: siempre `REFERENCIA_MANUAL`.
4. No inventar URLs — solo añadir fuentes verificadas manualmente.
5. Actualizar este documento (tabla de categorías y tabla de módulos).
