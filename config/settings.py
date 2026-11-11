import os
from pathlib import Path
from urllib.parse import unquote, urlparse
from django.core.exceptions import ImproperlyConfigured
from .env import load_env

BASE_DIR = Path(__file__).resolve().parent.parent
load_env(BASE_DIR / ".env")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "local-development-only-never-deploy-this-key"
    else:
        raise ImproperlyConfigured("Define DJANGO_SECRET_KEY antes de iniciar.")
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-")):
    raise ImproperlyConfigured(
        "En producción se exige un secreto aleatorio de al menos 50 caracteres."
    )
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"
    ).split(",")
    if host.strip()
]
# Render terminates TLS at its trusted edge proxy and forwards this header to
# the container. Respect it so Django's HTTPS redirect and secure cookies work.
if os.environ.get("RENDER") == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_hostname and render_hostname not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(render_hostname)
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "cemetery",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "cemetery.middleware.SessionLifetimeMiddleware",
    "cemetery.middleware.FamilyPortalBoundaryMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "cemetery.context.navigation",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
database_url = os.environ.get(
    "DATABASE_URL", "postgresql://cementerio@127.0.0.1:55432/cementerio"
)
db = urlparse(database_url)
if db.scheme not in ("postgres", "postgresql"):
    raise ImproperlyConfigured("DATABASE_URL debe usar PostgreSQL.")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(db.path.lstrip("/")),
        "USER": unquote(db.username or ""),
        "PASSWORD": unquote(db.password or ""),
        "HOST": db.hostname or "127.0.0.1",
        "PORT": db.port or 5432,
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"sslmode": os.environ.get("DATABASE_SSLMODE", "prefer")},
    }
}
AUTH_USER_MODEL = "cemetery.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DATA_UPLOAD_MAX_MEMORY_SIZE = 9 * 1024 * 1024
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/ingresar/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/ingresar/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CEMETERY_NAME = os.environ.get("CEMETERY_NAME", "CementerioERP")
CEMETERY_CURRENCY = os.environ.get("CEMETERY_CURRENCY", "COP")
CEMETERY_EXPIRY_DAYS = int(os.environ.get("CEMETERY_EXPIRY_DAYS", "30"))
CEMETERY_MOVEMENTS_APPROVED = os.environ.get("CEMETERY_MOVEMENTS_APPROVED", "0") == "1"
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "acceso@localhost")
