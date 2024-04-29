# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django DEVELOPMENT settings for maas project."""

import os
from os.path import abspath

from formencode.validators import StringBool

from maasserver.djangosettings import (
    fix_up_databases,
    import_settings,
    settings,
)

# We expect the following settings to be overridden. They are mentioned here
# to silence lint warnings: import_settings() below will actually re-set it
# to a tuple as set in settings.INSTALLED_APPS, and TEMPLATES to a dict.
INSTALLED_APPS = None
MIGRATION_MODULES = {}
TEMPLATES = {}

# Extend base settings.
import_settings(settings)

prevent_migrations = StringBool().to_python(
    os.environ.get("MAAS_PREVENT_MIGRATIONS", 0)
)

if prevent_migrations:
    INSTALLED_APPS += ("maasserver.tests", "metadataserver.tests")

# Use our custom test runner, which makes sure that a local database
# cluster is running in the branch.
TEST_RUNNER = "maastesting.djangoloader.MAASDjangoTestRunner"

# Don't connect to the DNS server in development because bind is not running
# and no access to write into the required directories.
DNS_CONNECT = False

# Don't setup DHCP servers in tests, this will be enabled on a case per case
# basis. TODO: Use the signals manager instead.
DHCP_CONNECT = os.environ.get("MAAS_DHCP_CONNECT", "0") == "1"

# Don't setup PROXY servers in tests, this will be enabled on a case per case
# basis. TODO: Use the signals manager instead.
PROXY_CONNECT = False

# Debugging: Log all query counts and time when enabled in the ENV. By default
# the development regiond will enable query logging, the unit tests will have
# it disabled.
DEBUG = True
DEBUG_QUERIES = os.environ.get("MAAS_DEBUG_QUERIES", "0") == "1"
DEBUG_QUERIES_LOG_ALL = (
    os.environ.get("MAAS_DEBUG_QUERIES_LOG_ALL", "0") == "1"
)

# Invalid strings should be visible.
TEMPLATES[0]["OPTIONS"]["string_if_invalid"] = "#### INVALID STRING ####"
STATIC_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "maasui",
    "build",
)

DATABASES = {
    "default": {
        # 'postgresql', 'mysql', 'sqlite3' etc.
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "maas",
        # For PostgreSQL, a "hostname" starting with a slash indicates a
        # Unix socket directory.
        "HOST": abspath("db"),
    }
}

INTERNAL_IPS = ("127.0.0.1", "::1")

# Make all nodes' metadata visible.  This is not safe; do not enable it
# on a production MAAS.
ALLOW_UNSAFE_METADATA_ACCESS = True

# Use in-branch preseed templates.
PRESEED_TEMPLATE_LOCATIONS = [abspath("package-files/etc/maas/preseeds")]

# Prevent migrations from running in development mode. This causes django to
# fallback to the syncdb behaviour. This is faster for development and a
# requirement for django >=1.7.
#
# Each module here points to a non-existing module. This just seems wrong, but
# this is exactly what django upstream does to test django.
prevent_migrations = StringBool().to_python(
    os.environ.get("MAAS_PREVENT_MIGRATIONS", 0)
)
if prevent_migrations:
    MIGRATION_MODULES = {
        "auth": "maastesting.empty",
        "contenttypes": "maastesting.empty",
        "sessions": "maastesting.empty",
        "sites": "maastesting.empty",
        "piston3": "maastesting.empty",
        "maasserver": "maastesting.empty",
        "maasserver.tests": "maastesting.empty",
        "metadataserver": "maastesting.empty",
        "metadataserver.tests": "maastesting.empty",
        "maastesting": "maastesting.empty",
    }
else:
    MIGRATION_MODULES["maastesting"] = "maastesting.migrations"

PASSWORD_HASHERS = (
    "django.contrib.auth.hashers.MD5PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
)

# This tells django-nose to load the given Nose plugins.
NOSE_PLUGINS = [
    "maastesting.noseplug.Crochet",
    "maastesting.noseplug.Resources",
    "maastesting.noseplug.Scenarios",
    "maastesting.noseplug.Select",
    "maastesting.noseplug.SelectBucket",
    "maastesting.noseplug.Subunit",
]

# Fix crooked settings.
fix_up_databases(DATABASES)
