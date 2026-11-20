"""Configuración de ARCHIVA. Variables de entorno controlan producción vs desarrollo."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("ARCHIVA_DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("ARCHIVA_SECRET_KEY", "dev-inseguro-cambiar-en-produccion")
if not DEBUG and SECRET_KEY.startswith("dev-"):
    raise RuntimeError("Defina ARCHIVA_SECRET_KEY en producción.")
ALLOWED_HOSTS = os.environ.get("ARCHIVA_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("ARCHIVA_CSRF_ORIGINS", "").split(",") if o]
# Railway: acepta automáticamente la dirección pública que le asigna el servicio.
_RAILWAY_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if _RAILWAY_DOMAIN:
    ALLOWED_HOSTS.append(_RAILWAY_DOMAIN)
    CSRF_TRUSTED_ORIGINS.append("https://" + _RAILWAY_DOMAIN)

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "core", "papeles",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
try:  # En producción (gunicorn) WhiteNoise sirve los estilos y gráficos de la interfaz
    import whitenoise  # noqa: F401
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
except ImportError:
    pass
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "core.context.navegacion",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

# Base de datos: PostgreSQL si hay ARCHIVA_DB_NAME, SQLite para desarrollo/demostración.
if os.environ.get("ARCHIVA_DB_NAME"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["ARCHIVA_DB_NAME"],
        "USER": os.environ.get("ARCHIVA_DB_USER", "archiva"),
        "PASSWORD": os.environ.get("ARCHIVA_DB_PASSWORD", ""),
        "HOST": os.environ.get("ARCHIVA_DB_HOST", "localhost"),
        "PORT": os.environ.get("ARCHIVA_DB_PORT", "5432"),
    }}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "data" / "db.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "es"
TIME_ZONE = "America/La_Paz"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Los documentos NO se sirven como /media: solo mediante vistas con control de acceso.
DOCUMENTOS_ROOT = Path(os.environ.get("ARCHIVA_DOCS_DIR", BASE_DIR / "data" / "documentos"))
MEDIA_ROOT = DOCUMENTOS_ROOT  # almacenamiento privado; sin MEDIA_URL público
BACKUP_DIR = Path(os.environ.get("ARCHIVA_BACKUP_DIR", BASE_DIR / "data" / "respaldos"))
MAX_UPLOAD_MB = int(os.environ.get("ARCHIVA_MAX_UPLOAD_MB", "50"))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_MB * 1024 * 1024
EXTENSIONES_PERMITIDAS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".txt"}

# OCR: "tesseract" usa pytesseract/ocrmypdf si están instalados; "none" lo desactiva.
OCR_MOTOR = os.environ.get("ARCHIVA_OCR", "tesseract")
OCR_IDIOMA = os.environ.get("ARCHIVA_OCR_LANG", "spa")

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_AGE = int(os.environ.get("ARCHIVA_SESSION_MIN", "30")) * 60  # control de sesiones
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
INTENTOS_LOGIN_MAX = 5
BLOQUEO_LOGIN_MIN = 15
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

if not DEBUG:  # cifrado de comunicaciones (HTTPS detrás de proxy inverso)
    SECURE_SSL_REDIRECT = os.environ.get("ARCHIVA_SSL_REDIRECT", "1") == "1"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_CONTENT_TYPE_NOSNIFF = True
