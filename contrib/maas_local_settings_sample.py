# Debug/Production mode.
DEBUG = False

# Default URL specifying protocol, host, and (if necessary) port where
# this MaaS can be found.  Configuration can, and probably should,
# override this.
DEFAULT_MAAS_URL = "http://maas.internal.example.com/"

# Absolute path to the directory static files should be collected to.
STATIC_ROOT = '/var/lib/maas/static/'

# Prefix to use for MaaS's urls.
# If FORCE_SCRIPT_NAME is None (the default), all the urls will start with
# '/'.
FORCE_SCRIPT_NAME = '/MaaS'

# Where to store the user uploaded files.
MEDIA_ROOT = '/var/lib/maas/media/'

# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize the logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(levelname)s %(asctime)s %(name)s %(message)s'
        },
    },
    'handlers': {
        'log': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/maas/maas.log',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'maas': {
            'handlers': ['log'],
            'propagate': True,
        },
        'django.request': {
            'handlers': ['log'],
            'propagate': True,
        },
        'django.db.backends': {
            'handlers': ['log'],
            'propagate': True,
        },
     }
}

# Database access configuration.
DATABASES = {
    'default': {
        # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' etc.
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': '',
        'USER': '',
        'PASSWORD': '',
        'HOST': 'localhost',
    }
}
