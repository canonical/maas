# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django DEVELOPMENT settings for maas project."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type

import logging
import os

from maas import (
    import_local_settings,
    import_settings,
    settings,
    )
from metadataserver.address import guess_server_address

# We expect the following settings to be overridden. They are mentioned here
# to silence lint warnings.
INSTALLED_APPS = None

# Extend base settings.
import_settings(settings)

# In development, django can be accessed directly on port 5240.
DEFAULT_MAAS_URL = "http://%s:5240/" % guess_server_address()

# Use our custom test runner, which makes sure that a local database
# cluster is running in the branch.
TEST_RUNNER = 'maastesting.runner.TestRunner'

# Use a fake provisioning server for test/demo purposes.
USE_REAL_PSERV = False

# Invalid strings should be visible.
TEMPLATE_STRING_IF_INVALID = '#### INVALID STRING ####'

DEBUG = True
TEMPLATE_DEBUG = DEBUG
YUI_DEBUG = DEBUG
STATIC_LOCAL_SERVE = True

RABBITMQ_PUBLISH = False

# Silent South during tests.
logging.getLogger('south').setLevel(logging.WARNING)

DATABASES = {
    'default': {
        # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' etc.
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'maas',
        # For PostgreSQL, a "hostname" starting with a slash indicates a
        # Unix socket directory.
        'HOST': '%s/db' % os.getcwd(),
    }
}

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = os.path.join(os.getcwd(), "media/development")

INSTALLED_APPS += (
    'django.contrib.admin',
    'maastesting',
    'debug_toolbar',
    'django_nose',
)

INTERNAL_IPS = ('127.0.0.1',)

DEBUG_TOOLBAR_CONFIG = {
    'INTERCEPT_REDIRECTS': False,
    }

# Allow the user to override settings in maas_local_settings.
import_local_settings()
