# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django DEVELOPMENT settings for maas project."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

import logging
from os.path import abspath

from maas import (
    fix_up_databases,
    import_settings,
    settings,
)
from maas.customise_test_db import patch_db_creation

# We expect the following settings to be overridden. They are mentioned here
# to silence lint warnings.
INSTALLED_APPS = None
LOGGING = None

# Extend base settings.
import_settings(settings)

# Use our custom test runner, which makes sure that a local database
# cluster is running in the branch.
TEST_RUNNER = 'maastesting.djangoloader.MAASDjangoTestRunner'

# Don't connect to the DNS server in tests, this will be enabled on a case per
# case basis.
DNS_CONNECT = False

# Don't setup DHCP servers in tests, this will be enabled on a case per case
# basis.
DHCP_CONNECT = False

# Invalid strings should be visible.
TEMPLATE_STRING_IF_INVALID = '#### INVALID STRING ####'

DEBUG = True
TEMPLATE_DEBUG = DEBUG
YUI_DEBUG = DEBUG
STATIC_LOCAL_SERVE = True

# Silent South during tests.
logging.getLogger('south').setLevel(logging.WARNING)

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

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = abspath("media/development")

INSTALLED_APPS += (
    'django.contrib.admin',
    'maastesting',
    'django_nose',
)

# Prevent 'No handlers could be found for logger ...' messages. By default,
# Nose clears all log handlers and captures logs itself. However, it doesn't
# change `propagate` which is set (once) by `configure_root_logger`.
LOGGING["loggers"]["maas"] = {"propagate": 1}

INTERNAL_IPS = ('127.0.0.1',)

# Make all nodes' metadata visible.  This is not safe; do not enable it
# on a production MAAS.
ALLOW_UNSAFE_METADATA_ACCESS = True

# Use in-branch preseed templates.
PRESEED_TEMPLATE_LOCATIONS = (
    abspath("etc/preseeds"),
    abspath("contrib/preseeds_v2"),
    )

# Inject custom code for setting up the test database.
patch_db_creation(abspath('db'), abspath('schema/baseline.sql'))

PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.MD5PasswordHasher',
)

# This tells django-nose to load the given Nose plugins.
NOSE_PLUGINS = [
    "maastesting.noseplug.Select",
]

# Fix crooked settings.
fix_up_databases(DATABASES)
