# Checklist: Modo test vs expediente real

## Tres niveles de madurez de un expediente

```
NIVEL 1 — BORRADOR TEST
  Sirve para: desarrollar, ensayar flujos, detectar faltantes estructurales.
  Estado de evidencia dominante: DECLARADO / ASUNCION_TEST
  Presentable: NO

NIVEL 2 — DOCUMENTO TÉCNICAMENTE SÓLIDO
  Sirve para: revisión técnica interna, validación metodológica.
  Estado de evidencia dominante: DECLARADO / INFERIDO con trazabilidad
  Presentable: NO — requiere confirmación de datos críticos

NIVEL 3 — EXPEDIENTE ADMINISTRATIVAMENTE PRESENTABLE
  Sirve para: presentar al órgano ambiental.
  Estado de evidencia: todos los campos críticos en CONFIRMADO o DECLARADO verificado
  Presentable: SÍ — solo si pasa checklist de presentabilidad completo
```

---

## Diferencias prácticas

### Titular / promotor
| Test | Real |
|------|------|
| "EMPRESA TEST, S.L." o nombre provisional | Nombre oficial del NIF verificado |
| AT activa cubriendo identidad | Sin AT — dato confirmado con documentación |

### Referencia catastral
| Test | Real |
|------|------|
| RC presente pero no verificada en Catastro | RC verificada en Sede Electrónica del Catastro |
| `rc_verificada=False` aceptado en test_mode | `rc_verificada=True` exigido en --prod |

### Coordenadas
| Test | Real |
|------|------|
| Coordenadas declaradas por promotor, no verificadas | Verificadas contra ortofoto PNOA o topografía |
| PENDIENTE aceptado en test | PENDIENTE bloquea gate en --prod |

### Cartografía
| Test | Real |
|------|------|
| Mapas generados con WMS disponible (puede ser provisional) | Fuente oficial identificada, fecha registrada, CRS correcto |
| Trazabilidad incompleta aceptada | `cartografia_trace.json` completo y sin huecos |

### Operaciones
| Test | Real |
|------|------|
| Operaciones declaradas por promotor, no verificadas con Registro de Producción | Verificadas o con AT explícita documentada |
| Código operativo puede ser estimado | Código legal base verificado con autorización administrativa |

### Impactos
| Test | Real |
|------|------|
| `INDETERMINADO` aceptable como estado intermedio | Todo impacto relevante valorado (COMPATIBLE/MODERADO/SEVERO/CRÍTICO) |
| Sin medida para impactos menores en test | Toda cadena: acción → impacto → medida → indicador PVA |

### Asunciones de test
| Test | Real |
|------|------|
| `at_activos` pueden existir — se documenta en scope | `at_activos = []` obligatorio — cero asunciones activas |
| `test_mode=True` en gate | `test_mode=False` (--prod) en gate |

### Auditoría
| Test | Real |
|------|------|
| Puede quedar como CON OBSERVACIONES sin bloquear | CONFORME requerido antes de ensamblar DOCX final |

---

## Regla de oro

> Si hay al menos una asunción de test activa, el expediente es TEST.
> Sin excepciones. No hay "test casi real".

---

## Frases que no deben aparecer en un expediente real

- "se asume que..."
- "a falta de datos se estima..."
- "valor provisional"
- "pendiente de verificación"
- "según lo declarado, sin confirmar"
- "AT-XXX activa"
- "ESTIMADO" en campos de identidad
- "NO DECLARADO" en modo, RC o coordenadas
