# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django settings for maas project."""

import os

from maasserver.config import RegionConfiguration
from maasserver.djangosettings import fix_up_databases
from maasserver.djangosettings.monkey import patch_get_script_prefix


def _read_timezone(tzfilename='/etc/timezone'):
    """Read a file whose contents is a timezone configuration, and return
    its contents (disregarding whitespace).
    """
    if os.path.isfile(tzfilename):
        try:
            with open(tzfilename, 'rb') as tzfile:
                return tzfile.read().decode('ascii').strip()
        except IOError:
            pass
    return None


def _get_local_timezone(tzfilename='/etc/timezone'):
    """Try to determine the local timezone, in the format of a zoneinfo
    file which must exist in /usr/share/zoneinfo. If a local time zone cannot
    be found, returns 'UTC'.
    """
    tz = _read_timezone(tzfilename=tzfilename)
    zoneinfo = os.path.join('usr', 'share', 'zoneinfo')
    # If we grabbed a string from /etc/timezone, ensure it exists in the
    # zoneinfo database before trusting it.
    if tz is not None and os.path.isfile(os.path.join(zoneinfo, tz)):
        return tz
    else:
        # If this fails, just use 'UTC', which should always exist.
        return 'UTC'


# Enable HA which uses the new rack controller and BMC code paths. This is a
# temporary measure to prevent conflicts during MAAS 2.0 development.
ENABLE_HA = True if int(os.environ.get('ENABLE_HA', 0)) == 1 else False

# Production mode.
DEBUG = False

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

# The following specify named URL patterns.
LOGOUT_URL = 'logout'
LOGIN_REDIRECT_URL = 'index'
LOGIN_URL = 'login'

# Should the DNS features be enabled?  Having this config option is a
# debugging/testing feature to be able to quickly disconnect the DNS
# machinery. TODO: Use the signals manager instead.
DNS_CONNECT = True

# Should the DHCP features be enabled?  Having this config option is a
# debugging/testing feature to be able to quickly disconnect the DNS
# machinery. TODO: Use the signals manager instead.
DHCP_CONNECT = True

# Should the PROXY features be enabled?  Having this config option is a
# debugging/testing feature to be able to quickly disconnect the PROXY
# machinery. TODO: Use the signals manager instead.
PROXY_CONNECT = True

# The MAAS CLI.
MAAS_CLI = 'sudo maas'

API_URL_PREFIX = '/api/2.0/'
METADATA_URL_PREFIX = '/metadata/'

# We handle exceptions ourselves (in
# maasserver.middleware.APIErrorsMiddleware)
PISTON_DISPLAY_ERRORS = False

# We have some backward-compatibility Piston handlers that necessarily use the
# same model, so we silence the warnings that Piston gives.
PISTON_IGNORE_DUPE_MODELS = True

YUI_DEBUG = DEBUG

# Set this to where YUI3 files can be found.
# Use a relative path (i.e. a path not starting with '/') to indicate a
# path relative to the 'static' directory.
# Use an absolute path (like '/usr/share/javascript/yui3/') to serve the files
# from a custom location.
YUI_LOCATION = '/usr/share/javascript/yui3/'

# Set this to where jQuery files can be found.
JQUERY_LOCATION = '/usr/share/javascript/jquery/'

# Set this to where AngularJS files can be found.
ANGULARJS_LOCATION = '/usr/share/javascript/angular.js/'

STATIC_LOCAL_SERVE = DEBUG

AUTHENTICATION_BACKENDS = (
    'maasserver.models.MAASAuthorizationBackend',
    'maasserver.views.macaroon_auth.MacaroonAuthenticationBackend',
)

# Database access configuration.
try:
    with RegionConfiguration.open() as config:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql_psycopg2',
                'NAME': config.database_name,
                'USER': config.database_user,
                'PASSWORD': config.database_pass,
                'HOST': config.database_host,
                'PORT': str(config.database_port),
                'CONN_MAX_AGE': config.database_conn_max_age,
            }
        }
except:
    # The regiond.conf will attempt to be loaded when the 'maas' command
    # is read by a standard user. We allow this to fail and miss configure the
    # database information. Django will still complain since no 'default'
    # connection is defined.
    DATABASES = {}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# Default set to the same timezone as the system.
TIME_ZONE = _get_local_timezone()

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Set the datetime format Django uses in templates to show the time in UTC.
# The format is consistent with what the websockets use.
DATETIME_FORMAT = 'D, d M. o H:i:s'

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL_PREFIX = '/static/'
# Serving of static files doesn't seem to grok how to compose a URL when a
# application is being served from a non-empty prefix (i.e. when request.path
# is not empty), so we have to hack this.
STATIC_URL = "/MAAS" + STATIC_URL_PREFIX

# Path to the root of the static files.
STATIC_ROOT = "/usr/share/maas/web/static"

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'zk@qw+fdhu_b4ljx+pmb*8sju4lpx!5zkez%&4hep_(o6y1nf0'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(os.path.dirname(__file__), "templates"),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                # Insert your TEMPLATE_CONTEXT_PROCESSORS here or use this
                # list if you haven't customized them:
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.request",
                "django.template.context_processors.static",
                # "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "maasserver.context_processors.yui",
                "maasserver.context_processors.global_options",
            ],
            'debug': DEBUG,
        },
    },
]

MIDDLEWARE_CLASSES = (

    # Used to append trailing slashes to URLs (APPEND_SLASH defaults on).
    'django.middleware.common.CommonMiddleware',

    # Used for session and cookies.
    'django.contrib.sessions.middleware.SessionMiddleware',

    # Used for to determine if a request requires protection against
    # CSRF attacks.
    'maasserver.middleware.CSRFHelperMiddleware',

    # Used for rendering API exceptions for maasserver Web API.
    'maasserver.middleware.APIErrorsMiddleware',

    # Used to display errors about disconnected clusters. FIXME: This should
    # not be done on every request!
    'maasserver.middleware.ExternalComponentsMiddleware',

    # Handle errors that should really be handled in application code:
    # NoConnectionsAvailable, PowerActionAlreadyInProgress, TimeoutError.
    # FIXME.
    'maasserver.middleware.RPCErrorsMiddleware',

    # Same as RPCErrorsMiddleware but for the Web API. FIXME.
    'maasserver.middleware.APIRPCErrorsMiddleware',

    # Used for rendering API exceptions for metadataserver Web API.
    'metadataserver.middleware.MetadataErrorsMiddleware',

    # Sets X-Frame-Options header to SAMEORIGIN.
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # Cookies to prevent CSRF.
    'django.middleware.csrf.CsrfViewMiddleware',

    # Creates request.user.
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    # Temporary messages. FIXME: Not sure if it's used.
    'django.contrib.messages.middleware.MessageMiddleware',

    # Demands a user for most web pages. The equivalent for the Web API is
    # handled by Piston.
    'maasserver.middleware.AccessMiddleware',

    # Compress responses.
    'django.middleware.gzip.GZipMiddleware',

    # Prints request & response to the logs. FIXME: Do we use this? Keep
    # DebuggingLoggerMiddleware underneath GZipMiddleware so that it deals
    # with un-compressed responses.
    'maasserver.middleware.DebuggingLoggerMiddleware',

)

ROOT_URLCONF = 'maasserver.djangosettings.urls'

SOUTH_MIGRATION_MODULES = {
    # Migrations before MAAS 2.0 are located in south sub-directory.
    'maasserver': 'maasserver.migrations.south.migrations',
    'metadataserver': 'metadataserver.migrations.south',
}

MIGRATION_MODULES = {
    # Migrations for MAAS >=2.0.
    'auth': 'maasserver.migrations.builtin.auth',
    'piston3': 'maasserver.migrations.builtin.piston3',
    'maasserver': 'maasserver.migrations.builtin.maasserver',
    'metadataserver': 'metadataserver.migrations.builtin',
}

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'maasserver',
    'metadataserver',
    'piston3',
)

if DEBUG:
    INSTALLED_APPS += (
        'django.contrib.admin',
    )

# See http://docs.djangoproject.com/en/dev/topics/logging for more details on
# how to customize the logging configuration. At present all logging config is
# handled elsewhere. Add ONLY Django-specific logging configration here.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'loggers': {
        # Django logs request errors but these are confusing because MAAS
        # automatically retries some requests if they're as a result of
        # serialisation failures and the like, plus MAAS itself logs request
        # failures but only once the request can no longer be retried. To
        # avoid log spam we limit `django.request` to critical events only.
        'django.request': {
            'level': 'CRITICAL',
        },
    },
}

# The duration, in minutes, after which we consider a commissioning node
# to have failed and mark it as FAILED_COMMISSIONING.
COMMISSIONING_TIMEOUT = 60

# Allow anonymous access to the metadata for a node, keyed by its MAC
# address.  This is for development purposes only.  DO NOT ENABLE THIS
# IN PRODUCTION or private metadata, including MAAS access credentials
# for all nodes, will be exposed on your network.
ALLOW_UNSAFE_METADATA_ACCESS = False

# Earlier locations in the following list will shadow, or overlay, later
# locations.
PRESEED_TEMPLATE_LOCATIONS = (
    "/etc/maas/preseeds",
    "/usr/share/maas/preseeds",
    )

# A list of strings representing the host/domain names that this Django
# site can serve.
# See https://docs.djangoproject.com/en/1.5/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ['*']

# Extend Django's JSON serialization.  Without this, JSON serialization of
# MAC addresses in model fields will break.
SERIALIZATION_MODULES = {
    'maasjson': 'maasserver.json',
}

# MAAS has no upload limit to allow for big image files.
# (Django 1.10 introduced this limit with a default of 2.5MB.)
DATA_UPLOAD_MAX_MEMORY_SIZE = None

# Patch the get_script_prefix method to allow twisted to work with django.
patch_get_script_prefix()

# Fix crooked settings.
fix_up_databases(DATABASES)
