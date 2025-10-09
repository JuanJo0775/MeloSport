"""
Django settings for MeloSport project.

Generado automáticamente con soporte para entorno de producción (Render)
y compatibilidad con PostgreSQL remoto, archivos estáticos, correo SMTP y seguridad HTTPS.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# ================================
# Paths y carga de .env
# ================================
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

# Cargar archivo .env
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ================================
# Configuración básica
# ================================
LANGUAGE_CODE = "es-co"   # Español de Colombia
TIME_ZONE = "America/Bogota"
USE_TZ = True
USE_L10N = True

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-key-dev")
DEBUG = os.getenv("DEBUG", "False").lower() in ("1", "true", "yes")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# Configuración HTTPS y proxy (Render)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host != "*"]

# Archivos estáticos y multimedia
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

AUTH_USER_MODEL = 'users.User'

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "apps.users.auth_backends.EmailOrUsernameModelBackend",
]

SESSION_COOKIE_AGE = 3600  # 1 hora
SESSION_SAVE_EVERY_REQUEST = True
PASSWORD_RESET_TIMEOUT = 1800  # 30 minutos

# ================================
# Apps instaladas
# ================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "django_select2",

    # Apps externas
    'rest_framework',
    'rest_framework_simplejwt',
    'django_filters',
    'corsheaders',

    # Apps internas
    "apps.common.apps.CommonConfig",
    'apps.backoffice',
    'apps.products',
    'apps.categories',
    'apps.reports',
    'apps.users',
    'apps.database',
    "apps.billing",
    'apps.api',
    'apps.frontend',
]

# ================================
# Django REST Framework + JWT
# ================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '1000/day',
        'contacto_rate_throttle': '4/hour',
    }
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ================================
# Middleware
# ================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ✅ agregado para servir estáticos
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "apps.users.middleware.AuditLogMiddleware",
]

# ================================
# Login / Logout
# ================================
LOGIN_URL = '/backoffice/login/'
LOGIN_REDIRECT_URL = '/backoffice/dashboard/'
LOGOUT_REDIRECT_URL = '/backoffice/login/'

ROOT_URLCONF = 'MeloSport.urls'

# ================================
# Templates
# ================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, "templates")],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'MeloSport.wsgi.application'

# ================================
# CORS
# ================================
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://127.0.0.1:8001,http://localhost:8001"
).split(",")

# ================================
# Database (Postgres compatible con Render)
# ================================
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "melosport_app"),
            "USER": os.getenv("DB_USER", "melosport_user"),
            "PASSWORD": os.getenv("DB_PASSWORD", "melosport@admin1010"),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }

# ================================
# Password validators
# ================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'users.validators.ComplexPasswordValidator'},
]

# ================================
# Internacionalización
# ================================
LANGUAGE_CODE = 'es'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = '.'
DECIMAL_SEPARATOR = ','
NUMBER_GROUPING = 3

AUDITLOG_SKIP_MODELS = {
    "AuditLog",
    "LogEntry",
    "Session",
    "ContentType",
    "Permission",
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ================================
# Configuración de correo (SMTP)
# ================================
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@melosport.com")

# ================================
# 🔒 Configuración de seguridad (Producción)
# ================================
SECURE_HSTS_SECONDS = 31536000  # Fuerza HTTPS durante 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
