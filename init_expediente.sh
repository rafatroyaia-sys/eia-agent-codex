#!/bin/bash
# ============================================================================
# EIA-AGENT v2.1 — Inicialización de expediente
# Ejecutar desde la raíz del proyecto de Claude Code
# ============================================================================

EXPEDIENTE_ID=$1

if [ -z "$EXPEDIENTE_ID" ]; then
  echo "Uso: ./init_expediente.sh EIA-2026-XXX"
  exit 1
fi

BASE_DIR="expediente-${EXPEDIENTE_ID}"

echo "Creando estructura para expediente: ${EXPEDIENTE_ID}"

# Estructura principal
mkdir -p "${BASE_DIR}/inputs/memorias"
mkdir -p "${BASE_DIR}/inputs/fotos"
mkdir -p "${BASE_DIR}/inputs/planos"
mkdir -p "${BASE_DIR}/inputs/otros"

mkdir -p "${BASE_DIR}/capas"

mkdir -p "${BASE_DIR}/mapas"
mkdir -p "${BASE_DIR}/clima"

mkdir -p "${BASE_DIR}/fichas_inventario"

mkdir -p "${BASE_DIR}/impactos"

mkdir -p "${BASE_DIR}/bloques"

mkdir -p "${BASE_DIR}/anejos/mapas"
mkdir -p "${BASE_DIR}/anejos/clima"
mkdir -p "${BASE_DIR}/anejos/impactos"
mkdir -p "${BASE_DIR}/anejos/PVA"
mkdir -p "${BASE_DIR}/anejos/fotos"
mkdir -p "${BASE_DIR}/anejos/coherencia"

mkdir -p "${BASE_DIR}/control_interno"

mkdir -p "${BASE_DIR}/output"

# Inicializar capas de datos vacías
echo "[]" > "${BASE_DIR}/capas/hechos_confirmados.json"
echo "[]" > "${BASE_DIR}/capas/inferencias_y_gaps.json"
echo "[]" > "${BASE_DIR}/capas/normativa_aplicable.json"
echo "[]" > "${BASE_DIR}/capas/matriz_trazabilidad.json"
echo "[]" > "${BASE_DIR}/capas/cartografia_trace.json"
echo "[]" > "${BASE_DIR}/capas/salidas_generadas.json"

# Inicializar log del orquestador
cat > "${BASE_DIR}/control_interno/log_orquestador.md" << 'EOF'
# Log del Orquestador — Expediente

| Timestamp | Fase | Agente | Acción | Resultado |
|-----------|------|--------|--------|-----------|
EOF

# Inicializar README
cat > "${BASE_DIR}/README_EXPEDIENTE.md" << EOF
# Expediente ${EXPEDIENTE_ID}

**Sistema**: EIA-Agent v2.1  
**Fecha de creación**: $(date +%Y-%m-%d)  
**Estado**: Fase 1 — Pendiente de ingesta  

## Estado de fases

| Fase | Estado | Gate |
|------|--------|------|
| 1. Ingesta | ⏳ pendiente | — |
| 2. Cierre objeto | ⏳ pendiente | 🔒 |
| 3. Triaje normativo | ⏳ pendiente | 🔒 |
| 4A. Cartografía | ⏳ pendiente | 🔒 |
| 4B. Clima | ⏳ pendiente | 🔒 |
| 5. Inventario | ⏳ pendiente | 🔒 |
| 6. Impactos/PVA | ⏳ pendiente | 🔒 |
| 7. Redacción | ⏳ pendiente | 🔒 |
| 8. Ensamblaje | ⏳ pendiente | 🔒 |
| 9. Auditoría | ⏳ pendiente | 🔒 |
EOF

echo ""
echo "✅ Estructura creada en: ${BASE_DIR}/"
echo ""
echo "Siguiente paso: copiar documentos del promotor a ${BASE_DIR}/inputs/"
echo "y ejecutar Fase 1 (AG-1 Ingesta)"
