# Instalación local — EIA-Agent v2.1

**Sistema**: EIA-Agent v2.1  
**Actualizado**: 2026-04-20  
**Nivel**: técnico ambiental (no se requieren conocimientos de programación)

---

## Requisito previo: Python 3.11 o superior

El sistema requiere **Python 3.11 o superior**. Antes de continuar, comprueba si ya lo tienes instalado:

- **Windows**: Abre el símbolo del sistema (cmd) y escribe `python --version`
- **macOS / Linux**: Abre Terminal y escribe `python3 --version`

Si no tienes Python o la versión es inferior a 3.11, descárgalo desde:  
https://www.python.org/downloads/

> **En Windows**: Durante la instalación, marca la casilla **"Add Python to PATH"** antes de hacer clic en "Install Now". Sin esta opción, el sistema no podrá encontrar Python.

---

## Instalación en Windows

1. Abre el **Explorador de archivos** y navega a la carpeta `proyecto-eia`.

2. Haz doble clic en el archivo **`install.bat`**.

3. Se abrirá una ventana negra (símbolo del sistema) que mostrará el progreso.

4. Al finalizar verás un resumen similar a este:

   ```
   OK     Python 3.13.x
   OK     Sistema operativo: Windows
   OK     venv creado
   OK     Dependencias instaladas correctamente.
   ```

5. Presiona cualquier tecla para cerrar.

Si la ventana se cierra sola sin mostrar nada, o muestra un error de Python no encontrado, consulta la sección [Problemas frecuentes](#problemas-frecuentes).

---

## Instalación en macOS / Linux

1. Abre una **Terminal** y navega a la carpeta del proyecto:

   ```bash
   cd ruta/a/proyecto-eia
   ```

2. La primera vez, da permiso de ejecución al instalador:

   ```bash
   chmod +x install.sh
   ```

3. Ejecuta el instalador:

   ```bash
   ./install.sh
   ```

4. Al finalizar verás el mismo resumen que en Windows.

---

## Crear el archivo `.env` con las claves API

El instalador crea el entorno pero **no configura las claves API automáticamente** — estas son personales y no deben guardarse en el código.

1. Localiza el archivo `.env.example` en la raíz del proyecto.

2. Cópialo como `.env`:
   - **Windows**: `copy .env.example .env`
   - **macOS/Linux**: `cp .env.example .env`

3. Abre `.env` con cualquier editor de texto (Bloc de notas, TextEdit, VS Code).

4. Rellena las claves que necesites (ver tabla de claves más abajo).

> **Importante**: nunca compartas ni subas el archivo `.env` a ningún repositorio. Contiene claves privadas.

### Claves API y para qué sirven

| Clave | Obligatoria | Para qué se usa |
|-------|------------|----------------|
| `AEMET_API_KEY` | Sí, para fase climática | Obtener datos climáticos de AEMET para el climograma y la clasificación climática del expediente |
| `MAPBOX_TOKEN` | No | Mapas base de alta resolución como fallback adicional (el sistema usa WMS institucionales por defecto) |
| `OPENAI_API_KEY` | No | Solo si se configura un agente alternativo GPT (el sistema usa Claude por defecto) |

**Cómo obtener la clave de AEMET:**
1. Ve a https://opendata.aemet.es/centrodedescargas/altaUsuario
2. Introduce tu correo y acepta los términos
3. Recibirás un correo con el enlace para activar la clave
4. Copia la clave en `.env` como `AEMET_API_KEY=TU_CLAVE_AQUI`

---

## Comprobar que la instalación fue correcta

Tras ejecutar el instalador, puedes verificar que todo funciona con este comando:

**Windows** (desde la raíz del proyecto):
```cmd
venv\Scripts\python tools\validate_expediente.py expediente-EIA-2026-RECIMETAL-NAVE-222
```

**macOS / Linux**:
```bash
venv/bin/python tools/validate_expediente.py expediente-EIA-2026-RECIMETAL-NAVE-222
```

Si la instalación fue correcta, verás algo similar a:
```
========== VALIDADOR EIA-Agent v2.1 ==========
Expediente: expediente-EIA-2026-RECIMETAL-NAVE-222
...
RESULTADO: VALIDO
```

---

## Activar el entorno virtual

Cada vez que abras una nueva terminal y quieras trabajar con el sistema, activa el entorno virtual:

**Windows**:
```cmd
venv\Scripts\activate
```

**macOS / Linux**:
```bash
source venv/bin/activate
```

Sabrás que está activado porque el prompt mostrará `(venv)` al principio.

Para desactivarlo cuando termines:
```
deactivate
```

---

## Problemas frecuentes

### Python no encontrado (Windows)

**Síntoma**: El instalador muestra "ERROR: Python no encontrado."

**Soluciones**:

1. Reinstala Python desde https://www.python.org/downloads/ y marca **"Add Python to PATH"** durante la instalación.

2. Si ya tienes Python instalado, puede que no esté en el PATH. Busca "Python" en el menú de inicio para encontrar el ejecutable y añade su carpeta al PATH manualmente.

---

### El comando `python` abre Microsoft Store (Windows)

**Síntoma**: Al escribir `python` en cmd se abre la Microsoft Store en lugar de Python.

**Solución**:
1. Ve a **Configuración > Aplicaciones > Alias de ejecución de aplicaciones**.
2. Desactiva `python.exe` y `python3.exe` (los que apuntan a la Store).
3. Instala Python desde https://www.python.org (no desde la Store).
4. Vuelve a ejecutar `install.bat`.

---

### Permiso denegado en macOS / Linux

**Síntoma**: Al ejecutar `./install.sh` aparece "Permission denied".

**Solución**:
```bash
chmod +x install.sh
./install.sh
```

---

### Fallo al instalar dependencias (sin conexión o error de red)

**Síntoma**: El instalador muestra "Fallo al instalar dependencias."

**Soluciones**:
1. Comprueba que tienes conexión a internet.
2. Si estás detrás de un proxy corporativo, configura las variables de entorno `HTTP_PROXY` y `HTTPS_PROXY` antes de ejecutar el instalador.
3. Si el problema persiste, instala las dependencias manualmente:
   ```bash
   venv/bin/pip install -r requirements.txt   # macOS/Linux
   venv\Scripts\pip install -r requirements.txt  # Windows
   ```

---

### El entorno virtual ya existe pero algo falla

**Síntoma**: El instalador dice que el venv ya existe pero hay errores posteriores.

**Solución**: Elimina la carpeta `venv/` y vuelve a ejecutar el instalador.
- Windows: `rmdir /s /q venv`
- macOS/Linux: `rm -rf venv`
