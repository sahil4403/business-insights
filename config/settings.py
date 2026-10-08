import os
from pathlib import Path
from dotenv import load_dotenv

"""
Django settings for config project.
Production Hardened & Audited Version.
"""

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv()

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

# Set DJANGO_ENABLE_HTTPS=True only when serving over HTTPS (e.g. behind nginx/caddy with SSL).
ENABLE_HTTPS = os.getenv("DJANGO_ENABLE_HTTPS", "False").lower() == "true"

# Trusted origins for POST/CSRF requests (scheme included).
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
# Safety net: apne saare hosts HTTPS origins me khud jud jayen taaki env
# miss hone par bhi same-site POST (login waghera) 403 na ho.
for _host in ALLOWED_HOSTS:
    _host = (_host or '').strip().lstrip('.')
    if _host and _host not in ('*', 'localhost', '127.0.0.1'):
        _origin = f'https://{_host}'
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)

# Cryptic Django 403 ki jagah Hinglish help page (cookie allow karo, dobara login).
CSRF_FAILURE_VIEW = 'authentication.views.csrf_failure_hinglish'


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'core',
    'master_data',
    'customers',
    'vehicles',
    'labour',
    'trips',
    'ledger',
    'expenses',
    'authentication',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "core.no_cache.NoCacheMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.StrictAdminSecurityMiddleware",
    "core.middleware.OperatorAccessMiddleware",
    "core.middleware.ViewerReadOnlyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.backup.AutoBackupMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "core.backends.CaseInsensitiveModelBackend",
    "django.contrib.auth.backends.ModelBackend",
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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
if os.getenv("DB_ENGINE", "mysql") == "sqlite":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.getenv('DB_NAME', str(BASE_DIR / 'db.sqlite3')),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv("DB_NAME"),
            'USER': os.getenv("DB_USER"),
            'PASSWORD': os.getenv("DB_PASSWORD"),
            'HOST': os.getenv("DB_HOST"),
            'PORT': os.getenv("DB_PORT"),
            # Persistent DB connections (per-request reconnect nahi) +
            # health check taaki stale connection kabhi error na de.
            'CONN_MAX_AGE': int(os.getenv("DB_CONN_MAX_AGE", "60")),
            'CONN_HEALTH_CHECKS': True,
        }
    }


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 12,
        },
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
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        # Non-manifest storage: missing collectstatic must never 500 the site.
        # WhiteNoise still compresses; un-hashed files get short cache (fresh in ~60s).
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}


# HTTPS Security Headers (Enabled only when DEBUG=False AND ENABLE_HTTPS=True)
if not DEBUG and ENABLE_HTTPS:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_REFERRER_POLICY = "same-origin"


# Email Configuration
EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")


# Production Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "production.log",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "WARNING",
    },
}


# Redirect URLs
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Sessions: expiry slides forward on every request (2 weeks from LAST
# activity, not from login) taaki active users randomly logout na hon.
SESSION_SAVE_EVERY_REQUEST = True
# Neeche wali values Django defaults ke barabar hain — explicitly likhi hain
# taaki "2 weeks sliding persistent login" ki guarantee code me dikhe aur
# future Django default change se tootey nahi. Behavior change ZERO hai.
# (Verified live: cookie me Expires + Max-Age=1209600 aata hai, DB expiry =
# login + 14 days. PDF download session key rotate nahi karta.)
SESSION_COOKIE_AGE = 1209600  # 2 weeks (seconds)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # browser/app background-close par cookie bana rahe
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# ---- Media (vehicle document uploads) ----
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
