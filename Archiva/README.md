# ARCHIVA — Sistema Integral de Gestión Documental Inteligente (MVP)

Prototipo funcional del plan empresarial ARCHIVA: Django + PostgreSQL, IA y OCR 100 % locales
(ningún documento sale del servidor, conforme a la residencia de datos en Bolivia).

## Inicio sencillo
Lea `INICIO-RAPIDO.txt` (o abra la carpeta con Claude Code y escriba "Ejecuta ARCHIVA"; el archivo `CLAUDE.md` le indica cómo).

## Probar en 2 minutos (modo demostración, SQLite)
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # dependencias, usuarios, archivo físico, expedientes y documentos de ejemplo
python manage.py runserver
```
Abrir http://127.0.0.1:8000 — usuarios `admin`, `archivista`, `funcionario`, `auditor`; clave `Archiva-2026!` (**cámbiela**).

## Instalación institucional (Docker)
```bash
cp .env.example .env     # editar claves y dominio
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```
Publicar detrás de nginx/caddy con HTTPS. Respaldos: programar con cron
`docker compose exec web python manage.py respaldar` (≥ 2 veces al día) y copiar el ZIP a un dispositivo
distinto; probar con `python manage.py verificar_respaldo <archivo.zip>`.

## Computadora y celular
- **Computadora / tableta grande:** versión completa — barra lateral azul (contraíble), buscador global, panel con gráficos, tablas completas.
- **Celular (pantallas ≤ 900 px):** versión ligera — menú desplegable, barra inferior (Inicio, Buscar, Documentos, Trámites, Más), indicadores y alertas sin gráficos pesados, y tablas convertidas en tarjetas de lectura fácil. Al registrar un documento desde el celular se puede fotografiar con la cámara.
- No requiere instalar nada: se abre desde el navegador del celular, con la misma cuenta.
- Probado en 1440, 820 y 390 px de ancho, sin desplazamiento horizontal.

## Módulo UAI: papeles de trabajo, referencias y marcas (nuevo)

Para la Unidad de Auditoría Interna de un GAM o GAD. Menú: **Papeles de trabajo (UAI)** (`/uai/`).
- **Marcas estandarizadas** en una tabla-índice ampliable (se retiran, no se borran).
- **Legajo permanente** (sección propia) y **legajo corriente** por auditoría. Al cargar un documento hay que elegir el tipo.
- **Numeración**: el código encabeza el título (`LP-A-003`, `LC1-C-001`) y todo se ordena por él.
- **Referencias y co-referencias con enlace**: un clic en la co-referencia lleva a la referencia de origen.
- **Marcas sugeridas** por reglas locales; el auditor las confirma o rechaza. No es IA generativa; el punto de conexión para OCR/IA está en `papeles/services.py: sugerir_marcas()`.
- **Objetivos fijos**; solo cambian mediante **adenda** aprobada por el administrador (jefe de la UAI).
- Verificador de consistencia, informe preliminar y descarga en **Excel** (libro con hipervínculos entre hojas) y **Word**.
- Todo queda en la bitácora de auditoría con cadena de hashes. Roles: administrador (aprueba), auditor (elabora), archivista (carga y consulta).

## Cobertura de requisitos (documento ARCHIVA)
| RF | Módulo | Estado |
|----|--------|--------|
| 001-002 | Usuarios, roles (Admin/Archivista/Funcionario/Auditor), dependencias | ✔ (altas vía /admin) |
| 003, 008 | Documentos, metadatos, almacenamiento privado, descarga con control de acceso, versionamiento | ✔ |
| 004 | Correspondencia (recepción/emisión, código automático) | ✔ |
| 005 | Trámites con derivación, recepción y trazabilidad | ✔ |
| 006 | Expedientes | ✔ |
| 007 | Archivo físico: estante → caja → carpeta, etiqueta QR, préstamos y devoluciones | ✔ |
| 009-010 | OCR (pypdf / Tesseract / OCRmyPDF) y IA local: tipo sugerido, resumen, metadatos con **revisión humana obligatoria** | ✔ (reglas; ver límites) |
| 011 | Búsqueda por contenido con ranking + asistente documental que respeta permisos | ✔ |
| 012 | Conservación: plazos de gestión/central, transferencias, alertas | ✔ |
| 013 | SHA-256, verificación de integridad, auditoría con cadena de hashes inmutable | ✔ |
| 014 | Reportes e inventario CSV | ✔ |
| 015 | API REST JSON con token Bearer (`/api/v1/documentos/`, `/api/v1/buscar/?q=`) | ✔ (lectura) |

Seguridad incluida: contraseñas ≥10 caracteres, bloqueo tras 5 intentos fallidos, sesión de 30 min,
HTTPS/HSTS/cookies seguras en producción, archivos fuera de rutas públicas, validación de extensión y tamaño,
acceso por dependencia y nivel (la búsqueda y la IA lo heredan), tokens de API guardados solo como hash.

## Límites honestos del MVP (siguientes pasos)
- **MFA** (en el plan): no implementado todavía; añadir TOTP (p. ej. `django-otp`).
- **IA**: clasificación por reglas y búsqueda TF-IDF. Para búsqueda semántica real, integrar embeddings locales
  + `pgvector`, y un LLM local (p. ej. vía Ollama) en `core/services.py` (`analizar_documento`, `responder_consulta`).
- **Cifrado en reposo** y respaldo incremental automático dependen de la infraestructura (disco cifrado, cron).
- Sin pruebas de carga ni auditoría de seguridad externa; interfaz sencilla (sin React). Validar con AGETIC
  y asesoría legal los requisitos normativos y de licenciamiento antes de comercializar.
- Cambie `ARCHIVA_SECRET_KEY` y las claves demo antes de cualquier uso real.
