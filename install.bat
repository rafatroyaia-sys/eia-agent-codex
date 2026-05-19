@echo off
setlocal EnableDelayedExpansion

echo.
echo   ============================================================
echo   EIA-Agent v2.1 -- Instalacion del entorno (Windows)
echo   ============================================================
echo.

:: Comprobar que Python esta disponible
python --version >nul 2>&1
if !errorlevel! neq 0 goto :sin_python

:: Capturar la version de Python para mostrarla
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VERSION=%%v

:: Si la version esta vacia, Python no esta correctamente instalado
if "!PY_VERSION!"=="" goto :sin_python

echo   Python !PY_VERSION! detectado.
echo.

:: Ejecutar el script de bootstrap
python scripts\setup_env.py
set SETUP_EXIT=!errorlevel!

if !SETUP_EXIT! neq 0 (
    echo.
    echo   ============================================================
    echo   La instalacion termino con errores.
    echo   Revisa los mensajes anteriores para solucionarlos.
    echo   ============================================================
    echo.
    pause
    exit /b !SETUP_EXIT!
)

echo.
echo   Instalacion completada. Presiona una tecla para cerrar.
pause >nul
exit /b 0

:sin_python
echo.
echo   ERROR: Python no encontrado.
echo.
echo   Posibles causas y soluciones:
echo.
echo   1. Python no esta instalado:
echo      - Descarga Python 3.11 o superior desde:
echo        https://www.python.org/downloads/
echo      - Durante la instalacion, marca:
echo        "Add Python to PATH"
echo.
echo   2. Python esta instalado pero no esta en PATH:
echo      - Reinstala Python y marca "Add to PATH".
echo.
echo   3. El comando "python" abre Microsoft Store:
echo      - Desactiva el alias de la Store en:
echo        Configuracion ^> Aplicaciones ^>
echo        Alias de ejecucion de aplicaciones
echo        (desactivar python.exe y python3.exe)
echo      - Luego instala Python desde python.org
echo.
echo   ============================================================
pause
exit /b 1
