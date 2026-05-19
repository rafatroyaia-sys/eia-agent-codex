#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_env.py -- INST-01 -- EIA-Agent v2.1
Bootstrap del entorno local para el proyecto proyecto-eia.

Uso:
    python scripts/setup_env.py          (desde la raiz del proyecto)
    python3 scripts/setup_env.py         (macOS/Linux)

Que hace:
    1. Verifica Python >= 3.11
    2. Detecta sistema operativo
    3. Crea venv/ en la raiz del proyecto (si no existe)
    4. Instala dependencias desde requirements.txt en el venv
    5. Verifica presencia de .env
    6. Comprueba claves API (sin bloquear si faltan)
    7. Imprime resumen y siguiente comando recomendado

No requiere dependencias externas. Solo libreria estandar.
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIGURACION
# ---------------------------------------------------------------------------

MIN_PYTHON = (3, 11)

# Claves API usadas por el sistema, con descripcion y si son criticas
API_KEYS = {
    "AEMET_API_KEY": {
        "descripcion": "AEMET -- necesaria para AG-07 (clima y climograma)",
        "critica": True,
    },
    "MAPBOX_TOKEN": {
        "descripcion": "Mapbox -- opcional (el sistema usa WMS institucionales por defecto)",
        "critica": False,
    },
    "OPENAI_API_KEY": {
        "descripcion": "OpenAI -- opcional (el sistema usa Claude por defecto)",
        "critica": False,
    },
}

# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

SEP  = "=" * 62
SEP2 = "-" * 62


def ok(msg: str) -> None:
    print(f"  OK     {msg}")


def warn(msg: str) -> None:
    print(f"  AVISO  {msg}")


def err(msg: str) -> None:
    print(f"  ERROR  {msg}")


def leer_env(env_file: Path) -> dict:
    """Lee un archivo .env y devuelve un dict de clave->valor."""
    resultado = {}
    try:
        with open(env_file, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    clave, _, valor = linea.partition("=")
                    resultado[clave.strip()] = valor.strip()
    except Exception:
        pass
    return resultado


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> int:
    print(f"\n{SEP}")
    print("  EIA-Agent v2.1 -- Bootstrap del entorno")
    print(f"{SEP}\n")

    # ── 1. Verificar version de Python ─────────────────────────────────────
    ver = sys.version_info
    ver_str = f"{ver.major}.{ver.minor}.{ver.micro}"

    if (ver.major, ver.minor) < MIN_PYTHON:
        err(f"Python {ver_str} detectado -- se requiere {MIN_PYTHON[0]}.{MIN_PYTHON[1]} o superior.")
        print()
        print("         Descarga: https://www.python.org/downloads/")
        print()
        return 1

    ok(f"Python {ver_str}")

    # ── 2. Detectar sistema operativo ──────────────────────────────────────
    sistema = platform.system()
    arquitectura = platform.machine()
    ok(f"Sistema operativo: {sistema} ({arquitectura})")

    # ── 3. Directorio del proyecto (padre de scripts/) ─────────────────────
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    ok(f"Directorio del proyecto: {project_root}")

    # ── 4. Crear o detectar venv ───────────────────────────────────────────
    venv_dir = project_root / "venv"
    venv_ya_existia = venv_dir.exists()

    print()

    if not venv_ya_existia:
        print("  Creando entorno virtual...")
        resultado = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            capture_output=True,
            text=True,
        )
        if resultado.returncode != 0:
            err("No se pudo crear el entorno virtual.")
            print()
            print(f"         {resultado.stderr.strip()}")
            print()
            print("         Posibles causas:")
            print("           - El modulo venv no esta disponible en esta instalacion de Python.")
            print("           - Permisos insuficientes en el directorio del proyecto.")
            return 1
        ok(f"Entorno virtual creado: {venv_dir}")
    else:
        ok(f"Entorno virtual ya existe: {venv_dir}")

    # ── 5. Rutas del pip y python del venv ────────────────────────────────
    if sistema == "Windows":
        venv_pip    = venv_dir / "Scripts" / "pip.exe"
        venv_python = venv_dir / "Scripts" / "python.exe"
        activar_cmd = f"venv\\Scripts\\activate"
    else:
        venv_pip    = venv_dir / "bin" / "pip"
        venv_python = venv_dir / "bin" / "python"
        activar_cmd = f"source venv/bin/activate"

    if not venv_pip.exists():
        err(f"pip no encontrado en el entorno virtual.")
        print(f"         Ruta esperada: {venv_pip}")
        print()
        print("         Solucion: elimina la carpeta 'venv/' y vuelve a ejecutar.")
        return 1

    # ── 6. Instalar dependencias desde requirements.txt ───────────────────
    req_file = project_root / "requirements.txt"

    if not req_file.exists():
        warn("requirements.txt no encontrado -- dependencias no instaladas.")
    else:
        print()
        print("  Instalando dependencias (puede tardar unos segundos)...")
        resultado = subprocess.run(
            [str(venv_pip), "install", "-r", str(req_file), "--quiet"],
            capture_output=True,
            text=True,
        )
        if resultado.returncode != 0:
            err("Fallo al instalar dependencias.")
            print()
            # Mostrar el final del error (los primeros 800 chars del stderr)
            stderr_recortado = resultado.stderr.strip()
            if len(stderr_recortado) > 800:
                stderr_recortado = "..." + stderr_recortado[-800:]
            print(f"         {stderr_recortado}")
            print()
            print("         Posibles causas:")
            print("           - Sin conexion a internet.")
            print("           - Paquete no compatible con Python", ver_str)
            print("           - Permisos insuficientes.")
            return 1
        ok("Dependencias instaladas correctamente.")

    # ── 7. Verificar .env ──────────────────────────────────────────────────
    print()
    env_file    = project_root / ".env"
    env_example = project_root / ".env.example"

    if env_file.exists():
        ok(".env encontrado.")
        env_vars = leer_env(env_file)
    else:
        env_vars = {}
        warn(".env no encontrado.")
        if env_example.exists():
            if sistema == "Windows":
                print("         Para crearlo: copy .env.example .env")
            else:
                print("         Para crearlo: cp .env.example .env")
        else:
            print("         Tampoco se encontro .env.example.")

    # ── 8. Verificar claves API ────────────────────────────────────────────
    print()
    print("  Claves API:")
    claves_faltantes_criticas = []

    for clave, info in API_KEYS.items():
        # Buscar en .env y en variables de entorno del sistema
        valor = env_vars.get(clave) or os.environ.get(clave, "")
        configurada = bool(valor and valor.strip())

        if configurada:
            print(f"    OK       {clave}")
        else:
            etiqueta = "CRITICA" if info["critica"] else "opcional"
            print(f"    AVISO    {clave} -- no configurada [{etiqueta}]")
            print(f"             {info['descripcion']}")
            if info["critica"]:
                claves_faltantes_criticas.append(clave)

    # ── 9. Resumen final ───────────────────────────────────────────────────
    print()
    print(f"{SEP}")
    print("  RESUMEN")
    print(f"{SEP}")
    print(f"  Python       : {ver_str}")
    print(f"  Sistema      : {sistema} ({arquitectura})")
    print(f"  venv         : {'ya existia' if venv_ya_existia else 'creado'}")
    print(f"               : {venv_dir}")
    print(f"  Dependencias : instaladas")
    print(f"  .env         : {'presente' if env_file.exists() else 'AUSENTE'}")

    if claves_faltantes_criticas:
        print(f"  Claves crit. : FALTANTES -> {', '.join(claves_faltantes_criticas)}")
        print(f"               : (configura en .env antes de usar los agentes que las requieren)")
    else:
        print(f"  Claves crit. : configuradas")

    print()
    print(f"  Siguiente paso:")
    print(f"    1. Activa el entorno virtual:")
    print(f"         {activar_cmd}")
    print(f"    2. Valida un expediente con:")
    print(f"         python tools/validate_expediente.py <ruta_expediente>")
    print(f"    3. (Opcional) Ejecuta el gate de una fase:")
    print(f"         python tools/run_gate.py <ruta_expediente> <fase>")
    print()
    print(f"{SEP}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
