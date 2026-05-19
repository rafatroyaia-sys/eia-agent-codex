# BRAND_ASSETS — Marca EcoGestión

## Identidad de marca

| Campo | Valor |
|-------|-------|
| **Nombre visual** | EcoGestión |
| **Subtítulo / tagline** | Impacto Positivo |
| **Ruta del logo** | `assets/brand/logo_ecogestion.png` |
| **Estado del archivo** | PENDIENTE — colocar manualmente en la ruta indicada |

---

## Colores visuales aproximados

| Color | Rol | Descripción |
|-------|-----|-------------|
| Verde ambiental | Principal | Identidad medioambiental; vegetación, naturaleza |
| Azul agua/clima | Secundario | Clima, hidrología, sostenibilidad hídrica |
| Blanco limpio | Fondo/texto | Legibilidad, formalidad técnica |

Los valores hex exactos deberán extraerse del archivo de logo una vez disponible. Estos colores son una referencia aproximada basada en la descripción visual de la marca.

---

## Usos recomendados

| Contexto | Uso | Estado |
|----------|-----|--------|
| Portada del informe ambiental (DOCX) | Logo en encabezado + subtítulo | Fase 8 (EN-06 pendiente) |
| Portada futura de la aplicación | Logo centrado en pantalla de bienvenida | P2/P3 |
| Pantalla de login futura | Logo reducido + nombre | P2/P3 |
| Documentación interna (control interno) | Logo en cabecera de documentos formales | Cuando esté disponible |
| Reportes de auditoría exportados | Logo en pie de página o portada | Fase 9 |

---

## Cómo añadir el logo

1. Coloca el archivo PNG en `assets/brand/logo_ecogestion.png`.
2. Resolución mínima recomendada: 300 dpi para impresión, 150 dpi para DOCX.
3. Fondo transparente (PNG con canal alfa) o fondo blanco.
4. El ensamblador DOCX (EN-06) leerá esta ruta automáticamente cuando esté implementado.

---

## Advertencia legal

> Revisar derechos y condiciones de uso de la marca "EcoGestión" antes de cualquier
> explotación comercial definitiva. El logo es propiedad del titular de la marca.
> Su uso en documentos técnicos internos o en software propio no implica cesión
> de derechos a terceros.

---

## Lo que NO contiene este repositorio

- El archivo de logo no está versionado en git (binario de marca).
- No hay credenciales, tokens ni claves en esta carpeta.
- Ver `docs/ENVIRONMENT_VARIABLES.md` para la gestión de secretos.
