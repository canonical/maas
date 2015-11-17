# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django settings for maas project."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

import os
from sys import stdout

import django.template
from maas import fix_up_databases
from maas.monkey import patch_get_script_prefix
from maasserver.config import RegionConfiguration
from provisioningserver.logger import (
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_FORMAT_DATE,
    DEFAULT_LOG_LEVEL,
)

# Use new style url tag:
# https://docs.djangoproject.com/en/dev/releases/1.3/#changes-to-url-and-ssi
django.template.add_to_builtins('django.templatetags.future')

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
# machinery.
DNS_CONNECT = True

# Should the DHCP features be enabled?  Having this config option is a
# debugging/testing feature to be able to quickly disconnect the DNS
# machinery.
DHCP_CONNECT = True

# The MAAS CLI.
MAAS_CLI = 'sudo maas-region-admin'

API_URL_REGEXP = '^/api/1[.]0/'
METADATA_URL_REGEXP = '^/metadata/'

# We handle exceptions ourselves (in
# maasserver.middleware.APIErrorsMiddleware)
PISTON_DISPLAY_ERRORS = False

# We have some backward-compatibility Piston handlers that necessarily use the
# same model, so we silence the warnings that Piston gives.
PISTON_IGNORE_DUPE_MODELS = True

TEMPLATE_DEBUG = DEBUG

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
    )

# Database access configuration.
with RegionConfiguration.open() as config:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': config.database_name,
            'USER': config.database_user,
            'PASSWORD': config.database_pass,
            'HOST': config.database_host,
            'PORT': '',
        }
    }

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = None

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL_PATTERN = '/static/'
# Serving of static files doesn't seem to grok how to compose a URL when a
# application is being served from a non-empty prefix (i.e. when request.path
# is not empty), so we have to hack this.
STATIC_URL = "/MAAS" + STATIC_URL_PATTERN

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

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    # 'django.template.loaders.eggs.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.request",
    "django.core.context_processors.media",
    "django.core.context_processors.static",
    # "django.core.context_processors.tz",
    "django.contrib.messages.context_processors.messages",
    "maasserver.context_processors.yui",
    "maasserver.context_processors.global_options",
)

MIDDLEWARE_CLASSES = (

    # Used to append trailing slashes to URLs (APPEND_SLASH defaults on).
    'django.middleware.common.CommonMiddleware',

    # Used for session and cookies.
    'django.contrib.sessions.middleware.SessionMiddleware',

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

ROOT_URLCONF = 'maas.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates"
    # or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(os.path.dirname(__file__), "templates"),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'maasserver',
    'metadataserver',
    'piston',
    'south',
)

if DEBUG:
    INSTALLED_APPS += (
        'django.contrib.admin',
    )

# See http://docs.djangoproject.com/en/dev/topics/logging for more details on
# how to customize the logging configuration.
#
# NOTE CAREFULLY that django.utils.log.DEFAULT_LOGGING is applied *before*
# applying the configuration below. This means that you need to mentally
# combine the settings in both DEFAULT_LOGGING and LOGGING to understand the
# resultant behaviour.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': DEFAULT_LOG_FORMAT,
            'datefmt': DEFAULT_LOG_FORMAT_DATE,
        },
    },
    'handlers': {
        'stdout': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'stream': stdout,
        },
    },
    'root': {
        'handlers': ['stdout'],
        'level': DEFAULT_LOG_LEVEL,
    },
    # Do *not* set any options for the `maas` logger here because config done
    # elsewhere -- by configure_root_logger() -- will be clobbered.
    'loggers': {
        'urllib3': {
            'level': 'WARN',
        },
        'nose': {
            'level': 'WARN',
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

# Patch the get_script_prefix method to allow twisted to work with django.
patch_get_script_prefix()

# Fix crooked settings.
fix_up_databases(DATABASES)
