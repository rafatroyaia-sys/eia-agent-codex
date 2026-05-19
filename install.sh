#!/usr/bin/env bash
# =============================================================================
# install.sh -- EIA-Agent v2.1 -- Bootstrap del entorno (macOS / Linux)
#
# Uso:
#   chmod +x install.sh    # solo la primera vez
#   ./install.sh
#
# Que hace:
#   Ejecuta scripts/setup_env.py con Python 3, que verifica la version,
#   crea el entorno virtual e instala las dependencias del proyecto.
# =============================================================================

echo ""
echo "  ============================================================"
echo "  EIA-Agent v2.1 -- Instalacion del entorno (macOS / Linux)"
echo "  ============================================================"
echo ""

# ── Detectar Python 3 ────────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    # En algunos sistemas python apunta a Python 3
    PY_VER=$(python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1 | cut -d. -f1)
    if [ "$PY_VER" = "3" ]; then
        PYTHON_CMD="python"
    else
        PYTHON_CMD=""
    fi
else
    PYTHON_CMD=""
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "  ERROR: Python 3 no encontrado."
    echo ""
    echo "  Instrucciones de instalacion:"
    echo ""
    echo "  macOS:"
    echo "    brew install python@3.11"
    echo "    O descarga desde: https://www.python.org/downloads/"
    echo ""
    echo "  Ubuntu / Debian:"
    echo "    sudo apt update && sudo apt install python3.11 python3.11-venv"
    echo ""
    echo "  Fedora / RHEL:"
    echo "    sudo dnf install python3.11"
    echo ""
    exit 1
fi

echo "  Python detectado: $($PYTHON_CMD --version 2>&1)"
echo ""

# ── Ejecutar setup_env.py ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! "$PYTHON_CMD" "$SCRIPT_DIR/scripts/setup_env.py"; then
    echo ""
    echo "  ============================================================"
    echo "  La instalacion termino con errores."
    echo "  Revisa los mensajes anteriores para solucionarlos."
    echo "  ============================================================"
    echo ""
    exit 1
fi
