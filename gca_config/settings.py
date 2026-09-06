import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'gca-genius-chess-academy-bilingual-2026-secret-key'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Genius Chess Academy Apps
    'core',
    'academy',
    'finance',
    'portal',
]

AUTH_USER_MODEL = 'academy.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # GCA Bilingual RTL/LTR Engine
    'core.middleware.BilingualMiddleware',
]

ROOT_URLCONF = 'gca_config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                
                # GCA Bilingual Context (CURRENT_LANG, IS_RTL, translations, formatters)
                'core.context_processors.bilingual_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'gca_config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr'
TIME_ZONE = 'Africa/Casablanca'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'portal:login'
LOGIN_REDIRECT_URL = 'portal:dashboard'
LOGOUT_REDIRECT_URL = 'portal:login'

CSRF_TRUSTED_ORIGINS = [
    'https://geniuschess.ma',
    'https://www.geniuschess.ma',
    'http://geniuschess.ma',
    'http://www.geniuschess.ma',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://127.0.0.1',
    'http://localhost',
]

CSRF_FAILURE_VIEW = 'portal.views.csrf_failure_view'

# Code de sécurité financier pour autoriser la modification des paiements
ADMIN_FINANCIAL_SECURITY_CODE = '6565'

# Configuration Passerelle WhatsApp Automatique (WAHA Local sur Ubuntu)
WHATSAPP_GATEWAY_URL = os.getenv('WHATSAPP_GATEWAY_URL', 'http://127.0.0.1:3000/api/sendText')
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN', '367c424698f14bf99a75902e14282110')
WHATSAPP_SESSION_NAME = os.getenv('WHATSAPP_SESSION_NAME', 'default')


