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
# to silence lint warnings.
INSTALLED_APPS = None

# Extend base settings.
import_settings(settings)

# Use our custom test runner, which makes sure that a local database
# cluster is running in the branch.
TEST_RUNNER = 'maastesting.djangoloader.MAASDjangoTestRunner'

# Don't connect to the DNS server in development because bind is not running
# and no access to write into the required directories.
DNS_CONNECT = False

# Don't setup DHCP servers in tests, this will be enabled on a case per case
# basis. TODO: Use the signals manager instead.
DHCP_CONNECT = False

# Don't setup PROXY servers in tests, this will be enabled on a case per case
# basis. TODO: Use the signals manager instead.
PROXY_CONNECT = False

# Invalid strings should be visible.
TEMPLATE_STRING_IF_INVALID = '#### INVALID STRING ####'

DEBUG = True
TEMPLATE_DEBUG = DEBUG
YUI_DEBUG = DEBUG
STATIC_LOCAL_SERVE = True

DATABASES = {
    'default': {
        # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' etc.
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'maas',
        # For PostgreSQL, a "hostname" starting with a slash indicates a
        # Unix socket directory.
        'HOST': abspath('db'),
    },
}

# Allow the database name to be overwritten using an environment variable.
# This is only used for test.e2e. This might be better handled by using
# RegionConfigurationFixture; see test_dbupgrade.py for an example.
if 'DEV_DB_NAME' in os.environ:
    DATABASES['default']['NAME'] = os.environ['DEV_DB_NAME']

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = abspath("media/development")

INTERNAL_IPS = ('127.0.0.1', '::1')

# Make all nodes' metadata visible.  This is not safe; do not enable it
# on a production MAAS.
ALLOW_UNSAFE_METADATA_ACCESS = True

# Use in-branch preseed templates.
PRESEED_TEMPLATE_LOCATIONS = (
    abspath("etc/preseeds"),
    abspath("contrib/preseeds_v2"),
    )

# Prevent migrations from running in development mode. This causes django to
# fallback to the syncdb behaviour. This is faster for development and a
# requirement for django >=1.7.
#
# Each module here points to a non-existing module. This just seems wrong, but
# this is exactly what django upstream does to test django.
prevent_migrations = StringBool().to_python(
    os.environ.get("MAAS_PREVENT_MIGRATIONS", 0))
if prevent_migrations:
    MIGRATION_MODULES = {
        'auth': 'maastesting.empty',
        'contenttypes': 'maastesting.empty',
        'sessions': 'maastesting.empty',
        'sites': 'maastesting.empty',
        'piston3': 'maastesting.empty',
        'maasserver': 'maastesting.empty',
        'metadataserver': 'maastesting.empty',
    }

PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.MD5PasswordHasher',
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
