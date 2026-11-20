# Actualización: módulo UAI (papeles de trabajo, referencias y marcas)

Es una app nueva (`papeles/`) que se suma a ARCHIVA sin cambiar su comportamiento actual.

## Archivos NUEVOS (copiar la carpeta completa)
- `papeles/` (modelos, vistas, plantillas, migraciones, pruebas y comando `seed_papeles`)
- `ACTUALIZACION-UAI.md` (este archivo)

## Archivos MODIFICADOS (reemplazar)
| Archivo | Qué cambió |
|---|---|
| `config/settings.py` | agrega `"papeles"` a `INSTALLED_APPS` |
| `config/urls.py` | agrega `path("", include("papeles.urls"))` |
| `core/context.py` | agrega el ítem de menú «Papeles de trabajo (UAI)» |
| `requirements.txt` | agrega `openpyxl` y `python-docx` |
| `Dockerfile.railway` | ejecuta `seed_papeles` al iniciar (datos de ejemplo) |
| `iniciar.sh`, `iniciar.bat` | ejecutan `seed_papeles` |
| `README.md`, `CLAUDE.md` | documentación |

## Cómo actualizar GitHub y Railway
1. En su repositorio, copie la carpeta `papeles/` y reemplace los archivos de la tabla (o suba el ZIP completo descomprimido).
2. `git add . && git commit -m "Módulo UAI: papeles de trabajo, referencias y marcas" && git push`
3. Railway vuelve a construir solo. Al iniciar, `migrate` crea las tablas nuevas y carga la tabla de marcas.
4. Entre como `admin` / `Archiva-2026!` y abra **Papeles de trabajo (UAI)** en el menú.

Si usa una base de datos con datos reales: la actualización solo agrega tablas; no modifica las existentes. Haga un respaldo antes (`python manage.py respaldar`).

## Qué probar primero
1. Abra la auditoría de ejemplo → papel `C-1.1` → **Sugerir marcas** → confirme una.
2. En `C-1.1`, en «Co-referencias», haga clic en `← C-1`: lo lleva a la línea de origen.
3. **Cargar documento al legajo**: no deja guardar sin elegir permanente o corriente.
4. Descargue el Excel: las referencias son enlaces entre hojas.

## Límites
- Las sugerencias son reglas (importes, sumas, respaldo), no IA generativa. Con `ARCHIVA_OCR=none` los documentos escaneados no tienen texto: cárguelo con OCR activado o transcríbalo.
- La tabla de marcas es una propuesta; debe contrastarse con el manual de la UAI y las guías de la CGE.
- En Word, las referencias se imprimen como texto (los hipervínculos entre papeles están en el Excel).
