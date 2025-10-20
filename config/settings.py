"""
Django settings for citizen affiliation service.
"""

import os
from pathlib import Path
import environ

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment variables
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-this-key")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party apps
    "rest_framework",
    "corsheaders",
    # Local apps
    "affiliation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
DATABASES = {"default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3")}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# In development, Django finds static files from installed apps automatically
# No need for STATICFILES_DIRS since we're using app static files

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}

# CORS
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# RabbitMQ Configuration
RABBITMQ_HOST = env("RABBITMQ_HOST", default="localhost")
RABBITMQ_PORT = env.int("RABBITMQ_PORT", default=5672)
RABBITMQ_USER = env("RABBITMQ_USER", default="guest")
RABBITMQ_PASSWORD = env("RABBITMQ_PASSWORD", default="guest")
RABBITMQ_VHOST = env("RABBITMQ_VHOST", default="/")

# RabbitMQ Queue Names
RABBITMQ_AFFILIATION_CREATED_QUEUE = env(
    "RABBITMQ_AFFILIATION_CREATED_QUEUE", default="affiliation.created"
)
RABBITMQ_USER_TRANSFERRED_QUEUE = env("RABBITMQ_USER_TRANSFERRED_QUEUE", default="user.transferred")
RABBITMQ_DOCUMENTS_DOWNLOAD_REQUESTED_QUEUE = env(
    "RABBITMQ_DOCUMENTS_DOWNLOAD_REQUESTED_QUEUE", default="documents.download.requested"
)
RABBITMQ_DOCUMENTS_READY_QUEUE = env("RABBITMQ_DOCUMENTS_READY_QUEUE", default="documents.ready")
RABBITMQ_REGISTER_CITIZEN_REQUESTED_QUEUE = env(
    "RABBITMQ_REGISTER_CITIZEN_REQUESTED_QUEUE", default="register.citizen.requested"
)
RABBITMQ_UNREGISTER_CITIZEN_REQUESTED_QUEUE = env(
    "RABBITMQ_UNREGISTER_CITIZEN_REQUESTED_QUEUE", default="unregister.citizen.requested"
)
RABBITMQ_REGISTER_CITIZEN_COMPLETED_QUEUE = env(
    "RABBITMQ_REGISTER_CITIZEN_COMPLETED_QUEUE", default="register.citizen.completed"
)
RABBITMQ_UNREGISTER_CITIZEN_COMPLETED_QUEUE = env(
    "RABBITMQ_UNREGISTER_CITIZEN_COMPLETED_QUEUE", default="unregister.citizen.completed"
)

# External API Configuration
# External API Configuration
GOVCARPETA_API_URL = os.getenv(
    "GOVCARPETA_API_URL", "https://govcarpeta-apis-4905ff3c005b.herokuapp.com"
)
DOCUMENT_SERVICE_URL = os.getenv("DOCUMENT_SERVICE_URL", "http://localhost:9000")

# Operator Configuration (Single operator system)
OPERATOR_ID = env("OPERATOR_ID", default="68f003d9a49e090002e5d0b5")
OPERATOR_NAME = env("OPERATOR_NAME", default="TEST DAGZ")

# Transfer Configuration
# URL that receiving operators will call to confirm successful transfer
# In production, set this to your actual domain (e.g., https://operator.example.com/api/v1/citizens/transfer/confirm/)
TRANSFER_CONFIRMATION_URL = env(
    "TRANSFER_CONFIRMATION_URL", default="http://localhost:8000/api/v1/citizens/transfer/confirm/"
)

# Logging Configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name} - {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "affiliation": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
