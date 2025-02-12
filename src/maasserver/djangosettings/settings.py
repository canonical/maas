# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django settings for maas project."""

import logging
import os
import pathlib

from django.core.exceptions import ImproperlyConfigured

from maasserver.config import get_db_creds_vault_path, RegionConfiguration
from maasserver.djangosettings import fix_up_databases
from maasserver.djangosettings.monkey import patch_get_script_prefix
from maasserver.vault import (
    get_region_vault_client,
    UnknownSecretPath,
    VaultError,
)
from provisioningserver.utils.env import MAAS_ID


def _read_timezone(tzfilename="/etc/timezone"):
    """Read a file whose contents is a timezone configuration, and return
    its contents (disregarding whitespace).
    """
    if os.path.isfile(tzfilename):
        try:
            with open(tzfilename, "rb") as tzfile:
                return tzfile.read().decode("ascii").strip()
        except OSError:
            pass
    return None


def _get_local_timezone(tzfilename="/etc/timezone"):
    """Try to determine the local timezone, in the format of a zoneinfo
    file which must exist in /usr/share/zoneinfo. If a local time zone cannot
    be found, returns 'UTC'.
    """
    tz = _read_timezone(tzfilename=tzfilename)
    zoneinfo = os.path.join("usr", "share", "zoneinfo")
    # If we grabbed a string from /etc/timezone, ensure it exists in the
    # zoneinfo database before trusting it.
    if tz is not None and os.path.isfile(os.path.join(zoneinfo, tz)):
        return tz
    else:
        # If this fails, just use 'UTC', which should always exist.
        return "UTC"


def _get_default_db_config(config: RegionConfiguration) -> dict:
    """Builds a default Django DB dict based on region configuration."""
    client = get_region_vault_client()
    # If fetching credentials from vault fails, use credentials from local configuration.
    database_user = config.database_user
    database_pass = config.database_pass
    database_name = config.database_name

    # Try fetching vault-stored credentials
    if client is not None:
        try:
            creds = client.get(get_db_creds_vault_path())
            # Override local configuration
            database_user = creds["user"]
            database_pass = creds["pass"]
            database_name = creds["name"]
        except KeyError as e:
            raise ImproperlyConfigured(  # noqa: B904
                f"Incomplete Vault-stored DB credentials, missing key {e}"
            )
        except UnknownSecretPath:
            # Vault does not have DB credentials, but is available. No need to report anything, use local credentials.
            pass
        except VaultError as e:
            # Vault entry is unavailable for some reason (misconfigured/sealed/wrong permissions).
            # Report and use local credentials.
            logging.getLogger(__name__).warning(
                "Unable to fetch DB credentials from Vault: ", exc_info=e
            )
            pass

    # Provide application name to PostgreSQL to check region activities
    maas_id = MAAS_ID.get() or "NO_ID"
    application_name = f"maas-regiond-{maas_id}"

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": database_name,
        "USER": database_user,
        "PASSWORD": database_pass,
        "HOST": config.database_host,
        "PORT": str(config.database_port),
        "CONN_MAX_AGE": config.database_conn_max_age,
        "OPTIONS": {
            "keepalives": int(config.database_keepalive),
            "keepalives_idle": config.database_keepalive_idle,
            "keepalives_interval": config.database_keepalive_interval,
            "keepalives_count": config.database_keepalive_count,
            "application_name": application_name,
        },
    }


# Enable HA which uses the new rack controller and BMC code paths. This is a
# temporary measure to prevent conflicts during MAAS 2.0 development.
ENABLE_HA = True if int(os.environ.get("ENABLE_HA", 0)) == 1 else False

# Debugging: Detailed error reporting, log all query counts and time
# when enabled, and optional log all HTTP requests and responses.
DEBUG = False
DEBUG_QUERIES = False
DEBUG_HTTP = False

# The following specify named URL patterns.
LOGOUT_URL = "/MAAS/"
LOGIN_URL = "/MAAS/"

# Always use X-Forwarded-Host when possible. This is needed
# when MAAS is setup behind a reverse proxy.
USE_X_FORWARDED_HOST = True

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
MAAS_CLI = "sudo maas"

# We handle exceptions ourselves (in
# maasserver.middleware.APIErrorsMiddleware)
PISTON_DISPLAY_ERRORS = False

# We have some backward-compatibility Piston handlers that necessarily use the
# same model, so we silence the warnings that Piston gives.
PISTON_IGNORE_DUPE_MODELS = True

AUTHENTICATION_BACKENDS = (
    "maasserver.auth.MAASAuthorizationBackend",
    "maasserver.macaroon_auth.MacaroonAuthorizationBackend",
)

# Database access configuration.
try:
    with RegionConfiguration.open() as config:
        DATABASES = {"default": _get_default_db_config(config)}
        DEBUG = config.debug
        DEBUG_QUERIES = config.debug_queries
        DEBUG_HTTP = config.debug_http
        if DEBUG_QUERIES and not DEBUG:
            # For debug queries to work debug most also be on, so Django will
            # track the queries made.
            DEBUG = True
        if DEBUG_HTTP and not DEBUG:
            # For HTTP debugging debug mode must also be on.
            DEBUG = True
except Exception:
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

# Offset-aware datetime objects are going to be the default in future Django
# versions.
USE_TZ = True

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-us"

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Set the datetime format Django uses in templates to show the time in UTC.
# The format is consistent with what the websockets use.
DATETIME_FORMAT = "D, d M. o H:i:s"

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Unset as media is stored in the database.
MEDIA_ROOT = ""

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ""

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
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# MAAS uses session storage for cookies, and no other crypto feature from
# Django, so the key is not used. The value is just a placeholder since Django
# doesn't allow empty values.
SECRET_KEY = "<UNUSED>"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "debug": DEBUG,
        },
    }
]

MIDDLEWARE = (
    # Update Prometheus metrics for requests
    "maasserver.prometheus.middleware.PrometheusRequestMetricsMiddleware",
    # Prints request & response to the logs. FIXME: Do we use this? Keep
    # DebuggingLoggerMiddleware underneath GZipMiddleware so that it deals
    # with un-compressed responses.
    "maasserver.middleware.DebuggingLoggerMiddleware",
    # Used for session and cookies.
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Used to append trailing slashes to URLs (APPEND_SLASH defaults on).
    "django.middleware.common.CommonMiddleware",
    # Used for rendering and logging exceptions.
    "maasserver.middleware.ExceptionMiddleware",
    # Ensure the connection of the service layer is open.
    "maasserver.middleware.ServiceLayerMiddleware",
    # Used to clear the RBAC thread-local cache.
    "maasserver.middleware.RBACMiddleware",
    # Handle errors that should really be handled in application code:
    # NoConnectionsAvailable, TimeoutError.
    # FIXME.
    "maasserver.middleware.RPCErrorsMiddleware",
    # Same as RPCErrorsMiddleware but for the Web API. FIXME.
    "maasserver.middleware.APIRPCErrorsMiddleware",
    # Used for to determine if a request requires protection against
    # CSRF attacks.
    "maasserver.middleware.CSRFHelperMiddleware",
    # Used to remove csrf cookies from responses,
    "maasserver.middleware.SuppressCSRFCookieMiddleware",
    # Used to add external auth info to the request, to avoid getting the
    # information in multiple places.
    "maasserver.middleware.ExternalAuthInfoMiddleware",
    # Cookies to prevent CSRF.
    "django.middleware.csrf.CsrfViewMiddleware",
    # Creates request.user.
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Demands a user for most web pages. The equivalent for the Web API is
    # handled by Piston.
    "maasserver.middleware.AccessMiddleware",
    # Sets X-Frame-Options header to SAMEORIGIN.
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
)

ROOT_URLCONF = "maasserver.djangosettings.urls"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MIGRATION_MODULES = {
    # Migrations for MAAS >=2.0.
    "auth": "maasserver.migrations.auth",
    "piston3": "maasserver.migrations.piston3",
    "maasserver": "maasserver.migrations.maasserver",
    "metadataserver": "metadataserver.migrations",
}

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    "maasserver",
    "metadataserver",
    "piston3",
)

SESSION_ENGINE = "maasserver.sessiontimeout"

# See http://docs.djangoproject.com/en/dev/topics/logging for more details on
# how to customize the logging configuration. At present all logging config is
# handled elsewhere. Add ONLY Django-specific logging configration here.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {
        # Django logs request errors but these are confusing because MAAS
        # automatically retries some requests if they're as a result of
        # serialisation failures and the like, plus MAAS itself logs request
        # failures but only once the request can no longer be retried. To
        # avoid log spam we limit `django.request` to critical events only.
        "django.request": {"level": "CRITICAL"},
        "django.template": {"level": "INFO"},
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
PRESEED_TEMPLATE_LOCATIONS = ("/etc/maas/preseeds", "/usr/share/maas/preseeds")

# A list of strings representing the host/domain names that this Django
# site can serve.
# See https://docs.djangoproject.com/en/1.5/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ["*"]

# Consider the request secure if the header is set
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# MAAS has no upload limit to allow for big image files.
# (Django 1.10 introduced this limit with a default of 2.5MB.)
DATA_UPLOAD_MAX_MEMORY_SIZE = None

# Force all resolved urls to be prefixed with 'MAAS/'.
# All *must* start and end with a '/'.
FORCE_SCRIPT_NAME = "/MAAS/"
API_URL_PREFIX = "/MAAS/api/2.0/"
METADATA_URL_PREFIX = "/MAAS/metadata/"
SIMPLESTREAMS_URL_PREFIX = "/MAAS/images-stream/"

# The path to the asset manifest file.
SNAP_MANIFEST_PATH = pathlib.Path(
    "/snap/maas/current/usr/share/maas/web/static/asset-manifest.json"
)
DEB_MANIFEST_PATH = pathlib.Path(
    "/usr/share/maas/web/static/asset-manifest.json"
)

MAAS_UI_MANIFEST_PATH = (
    DEB_MANIFEST_PATH if DEB_MANIFEST_PATH.exists() else SNAP_MANIFEST_PATH
)

# Patch the get_script_prefix method to allow twisted to work with django.
patch_get_script_prefix()

# Fix crooked settings.
fix_up_databases(DATABASES)
