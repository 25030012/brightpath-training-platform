import os
import socket
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "brightpath-dev-secret-key-hw4")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
ROOT_URLCONF = "brightpath.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "core" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
                "core.auth.auth_context",
            ],
        },
    },
]


def _can_connect_postgres(sock_path="/tmp/.s.PGSQL.5433"):
    if os.environ.get("FORCE_SQLITE") == "1":
        return False
    if not os.path.exists(sock_path):
        return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.2)
        s.connect(sock_path)
        s.close()
        return True
    except OSError:
        return False


if _can_connect_postgres():
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("PGDATABASE", "brightpath"),
            "USER": os.environ.get("PGUSER", "postgres"),
            "HOST": os.environ.get("PGHOST", "/tmp"),
            "PORT": os.environ.get("PGPORT", "5433"),
        }
    }
else:
    # shortcut: fallback to SQLite when macOS Seatbelt sandbox blocks unix/TCP sockets, upgrade to PG when running on host
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = False

STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
