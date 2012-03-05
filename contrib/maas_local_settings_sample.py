# Absolute path to the directory static files should be collected to.
STATIC_ROOT = '/var/lib/maas/static/'

# Prefix to use for MaaS's urls.
# If FORCE_SCRIPT_NAME is None (the default), all the urls will start with
# '/'.
FORCE_SCRIPT_NAME = None
# FORCE_SCRIPT_NAME = '/MaaS'

# Where to store the user uploaded files.
MEDIA_ROOT = '/var/tmp/maas'

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
