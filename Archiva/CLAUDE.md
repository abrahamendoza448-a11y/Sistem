# ARCHIVA — instrucciones para Claude Code

Sistema de gestión documental municipal (Django). Proyecto de una persona que NO programa: explique todo en español sencillo.

## Cuando el usuario pida "ejecuta / inicia / abre ARCHIVA"
1. Ejecute `./iniciar.sh` (Linux/Mac) o `iniciar.bat` (Windows). Crea el entorno, instala dependencias, prepara datos de ejemplo y arranca el servidor.
2. Avise que debe abrir http://127.0.0.1:8000 en el navegador. Usuarios de demostración: admin, archivista, funcionario, auditor — clave `Archiva-2026!`.
3. Para probar desde un celular en la misma Wi-Fi: `./iniciar.sh --red` (o `iniciar.bat red`) y use la dirección que se imprime.
4. Para detener: Ctrl + C.

## Comandos útiles
- Pruebas: `python manage.py test core` (deben pasar las 30; `python manage.py test papeles` solo el módulo UAI)
- Respaldo: `python manage.py respaldar` · Verificar: `python manage.py verificar_respaldo <zip>`
- Datos de ejemplo: `python manage.py seed_demo`

## Estructura
- `core/models.py` datos · `core/views.py` pantallas · `core/services.py` permisos, OCR, IA local, búsqueda
- `core/templates/` HTML · `core/static/core/archiva.css` estilos (escritorio completo, móvil ligero ≤ 900 px)
- `config/settings.py` configuración (SQLite en demo; PostgreSQL con `ARCHIVA_DB_NAME`)

- `papeles/` módulo UAI (marcas, legajos, referencias, adendas). Datos de ejemplo: `python manage.py seed_papeles`

## Reglas
- Todo el procesamiento (OCR/IA) es local: no enviar documentos a servicios externos.
- La búsqueda y la IA siempre pasan por `documentos_visibles()` (permisos). No saltarlo.
- La auditoría es inmutable: no agregar borrados ni ediciones sobre `Auditoria`.
- No subir `data/` ni `.env` a ningún repositorio.
- Antes de cambios grandes, correr las pruebas.
- Los objetivos y adendas del módulo `papeles` son inmutables; no agregar edición ni borrado, solo nuevas adendas.
- Las marcas sugeridas nunca se confirman solas: la confirmación es del auditor.
