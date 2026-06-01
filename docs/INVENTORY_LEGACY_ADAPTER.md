# Adaptador de Inventario Legacy

`inventory_legacy_adapter.py` permite reutilizar expedientes avanzados o pilotos
que ya tienen `fichas_inventario/indice_inventario.json`, pero todavía no tienen
el output productizado `inventario/inventory_summary.json`.

## Qué hace

- Lee las 16 fichas AG-08 desde `fichas_inventario/indice_inventario.json`.
- Convierte cada factor a `FactorInventory`.
- Conserva `estado_evidencia`, `semaforo`, `hc_base`, `cautelas`, `pendientes`,
  `gaps_bloqueantes` y `nota_test`.
- Escribe `inventario/inventory_summary.json` si se ejecuta con escritura.
- No declara aptitud administrativa.

## Reglas de prudencia

- `gaps_bloqueantes` se traducen como gaps `ALTA` y `PENDIENTE`.
- Un factor `ROJO` o con gap `ALTA` no se marca como listo para Fase 6 aunque el
  índice histórico indicase `apto_ag09=true`.
- Los pendientes se conservan como gaps `MEDIA`.
- Las cautelas se mantienen como warnings del factor.

## Integración

`inventory-build --write` usa este adaptador automáticamente cuando falta
`fase4/phase4_result.json` pero existe `fichas_inventario/indice_inventario.json`.

Esto evita que un expediente antiguo se bloquee por incompatibilidad de carpetas,
sin maquillar debilidades técnicas ni elevar estados de evidencia.

