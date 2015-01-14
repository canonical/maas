# Default URL specifying protocol, host, and (if necessary) port where
# systems in this MAAS can find the MAAS server.  Configuration can, and
# probably should, override this.
DEFAULT_MAAS_URL = "http://maas.internal.example.com/"

# Absolute path to the directory static files should be collected to.
STATIC_ROOT = '/usr/share/maas/web/static/'

# Where to store the user uploaded files.
MEDIA_ROOT = '/var/lib/maas/media/'

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
