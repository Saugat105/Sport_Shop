"""
Django settings for core project.

Works in BOTH development (local) and production (Render).
- Locally: SQLite + console email + DEBUG=True
- On Render: Postgres + Gmail SMTP + DEBUG=False
"""

from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════════
# CORE SECURITY SETTINGS
# ═══════════════════════════════════════════════════════════════

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-secret-key-change-me-in-production')
DEBUG      = os.environ.get('DEBUG', 'True') == 'True'   # Default True for local dev

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '.onrender.com',
]

CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
]


# ═══════════════════════════════════════════════════════════════
# APPLICATIONS
# ═══════════════════════════════════════════════════════════════

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'crispy_forms',
    'crispy_bootstrap5',
    

    # Local
    'shop',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',          # serves static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'shop.middleware.NoCacheLoggedInMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# ═══════════════════════════════════════════════════════════════
# DATABASE
# Reads DATABASE_URL on Render (Postgres), falls back to SQLite locally
# ═══════════════════════════════════════════════════════════════

DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
        ssl_require=not DEBUG,   # SSL only in production
    )
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ═══════════════════════════════════════════════════════════════
# AUTHENTICATION
# ═══════════════════════════════════════════════════════════════

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTHENTICATION_BACKENDS = [
    'shop.auth_backends.UsernameOrEmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL           = 'login'
LOGIN_REDIRECT_URL  = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'


# ═══════════════════════════════════════════════════════════════
# INTERNATIONALIZATION
# ═══════════════════════════════════════════════════════════════

LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Asia/Kathmandu'   # ← your local timezone for correct dates/times
USE_I18N      = True
USE_TZ        = True


# ═══════════════════════════════════════════════════════════════
# STATIC FILES (CSS, JS) — WhiteNoise for production
# ═══════════════════════════════════════════════════════════════

STATIC_URL       = '/static/'
STATIC_ROOT      = BASE_DIR / 'staticfiles'   # where collectstatic puts files
STATICFILES_DIRS = [BASE_DIR / 'static']

# Compresses + cache-busts files in production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# ═══════════════════════════════════════════════════════════════
# CRISPY FORMS
# ═══════════════════════════════════════════════════════════════

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK          = 'bootstrap5'


# ═══════════════════════════════════════════════════════════════
# REST FRAMEWORK
# ═══════════════════════════════════════════════════════════════

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}


# ═══════════════════════════════════════════════════════════════
# EMAIL
# Locally (DEBUG=True): prints to console — easy testing
# In production (DEBUG=False): real Gmail SMTP
# ═══════════════════════════════════════════════════════════════

if DEBUG:
    # Development: emails print to terminal
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    # Production: real email via Gmail SMTP
    EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST          = 'smtp.gmail.com'
    EMAIL_PORT          = 587
    EMAIL_USE_TLS       = True
    EMAIL_HOST_USER     = os.environ.get('EMAIL_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
    EMAIL_TIMEOUT       = 10  # seconds

DEFAULT_FROM_EMAIL = f"Sport Shop Nepal <{os.environ.get('EMAIL_USER', 'noreply@sportshop.com')}>"


# ═══════════════════════════════════════════════════════════════
# SITE URL (used for verification email links)
# ═══════════════════════════════════════════════════════════════

SITE_URL = os.environ.get('SITE_URL', 'http://127.0.0.1:8000')


# ═══════════════════════════════════════════════════════════════
# PRODUCTION SECURITY
# ═══════════════════════════════════════════════════════════════

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT     = True
    SESSION_COOKIE_SECURE   = True
    CSRF_COOKIE_SECURE      = True
    SECURE_HSTS_SECONDS     = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD     = True
    X_FRAME_OPTIONS         = 'DENY'