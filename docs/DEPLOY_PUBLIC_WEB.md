# Deploy publico de EIA-Agent Cliente

El objetivo de este despliegue es entregar al cliente una URL publica. El
cliente no instala Python, no ejecuta archivos BAT y no trabaja con carpetas
tecnicas.

## Arquitectura

- Un unico servicio web sirve frontend y API desde el mismo dominio.
- Docker garantiza un entorno reproducible.
- Render construye y despliega automaticamente desde GitHub.
- La primera publicacion usa el servicio gratuito para poder probar la app sin tarjeta.
- El servicio publica un health check en `/api/health`.

## Despliegue recomendado

Acceso directo:

[Desplegar EIA-Agent Cliente en Render](https://render.com/deploy?repo=https://github.com/rafatroyaia-sys/eia-agent-codex)

1. Crear una cuenta o iniciar sesion en Render.
2. Conectar la cuenta GitHub que tiene acceso a:
   `rafatroyaia-sys/eia-agent-codex`.
3. En Render, seleccionar `New > Blueprint`.
4. Conectar el repositorio.
5. Confirmar el Blueprint detectado desde `render.yaml`.
6. Introducir una clave privada en la variable `EIA_ACCESS_TOKEN`.
7. Pulsar `Deploy Blueprint`.

Render asignara una URL similar a:

```text
https://eia-agent-cliente.onrender.com
```

Cada nuevo `git push` puede desplegar automaticamente la nueva version.

El cliente introduce la clave de acceso en la cabecera de la app. El navegador
la guarda localmente y la API rechaza la creacion/listado/subida de expedientes
si la clave no coincide.

## Primera prueba gratuita

El Blueprint utiliza el plan gratuito de Render y no solicita tarjeta. Permite
probar la URL publica, el frontend, la creacion de expedientes y las subidas.

Importante: en la version gratuita, los archivos pueden borrarse cuando Render
reinicie o vuelva a desplegar la app. Antes de entregar el producto definitivo
al cliente se conectara almacenamiento permanente.

Mientras se mantenga el plan gratuito, la app permite descargar una
`COPIA_COMPLETA.zip` de cada expediente y restaurarla desde la propia pantalla.
La copia incluye inputs, fotos, cartografia, controles internos y documentos
generados.

## Paso a produccion con almacenamiento permanente

La configuracion preparada esta en `render.production.yaml`. Para la entrega
definitiva al cliente:

1. Cambiar el servicio de Render de `Free` a un plan de pago compatible.
2. En `Disks`, anadir un disco con ruta de montaje `/var/data`.
3. Crear la variable `EIA_PERSISTENT_STORAGE=true`.
4. Confirmar que la cabecera de la app muestra `Archivos: almacenamiento permanente`.

Render conserva los archivos escritos bajo `/var/data` entre reinicios y
despliegues, cifra el disco y crea snapshots diarios. El disco no sustituye a
las copias completas descargables: conviene conservar ambas protecciones.

## Comprobaciones

Tras el despliegue:

```text
GET /api/health
```

Debe responder con `ok: true`.

La pagina principal debe mostrar la app de alta de expedientes y permitir:

- introducir datos del proyecto,
- validar coordenadas y requisitos minimos,
- subir memorias, fotos, planos y cartografia,
- crear el expediente en backend,
- conservar los inputs en almacenamiento persistente.

## Alcance actual

El servicio web crea y organiza expedientes reales. La generacion automatica
completa del Documento Ambiental, cartografia oficial, climograma, matrices,
DOCX y auditoria se conectara progresivamente al pipeline existente respetando
todos los gates tecnicos.

La app no declara automaticamente aptitud administrativa.
