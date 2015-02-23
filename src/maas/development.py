# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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
    import_local_settings,
    import_settings,
    settings,
    )
from maas.customise_test_db import patch_db_creation
from metadataserver.address import guess_server_host
import provisioningserver.config
from provisioningserver.utils.url import compose_URL

# We expect the following settings to be overridden. They are mentioned here
# to silence lint warnings.
INSTALLED_APPS = None

# Extend base settings.
import_settings(settings)

# In development, django can be accessed directly on port 5240.
DEFAULT_MAAS_URL = compose_URL("http://:5240/MAAS/", guess_server_host())

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
    'debug_toolbar',
    'django_nose',
)

INTERNAL_IPS = ('127.0.0.1',)

DEBUG_TOOLBAR_CONFIG = {
    'INTERCEPT_REDIRECTS': False,
    }

DEBUG_TOOLBAR_PANELS = (
    'debug_toolbar.panels.versions.VersionsPanel',
    'debug_toolbar.panels.timer.TimerPanel',
    'debug_toolbar.panels.settings.SettingsPanel',
    'debug_toolbar.panels.headers.HeadersPanel',

    # XXX: allenap 2015-01-16 bug=1411668: RequestPanel uses the database in
    # process_response() without considering if the database is in a fit state
    # to be used, i.e. the transaction is broken. Hence it has been disabled
    # temporarily.
    # 'debug_toolbar.panels.request.RequestPanel',

    'debug_toolbar.panels.sql.SQLPanel',

    # XXX: allenap 2015-01-16 bug=1411668: RPCPanel uses the database in
    # process_response() without considering if the database is in a fit state
    # to be used, i.e. the transaction is broken. Hence it has been disabled
    # temporarily.
    # 'maasserver.rpc.testing.debug_panel.RPCPanel',

    'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.cache.CachePanel',
    'debug_toolbar.panels.signals.SignalsPanel',
    'debug_toolbar.panels.logging.LoggingPanel',
    'debug_toolbar.panels.redirects.RedirectsPanel',
)

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

# Allow the user to override settings in maas_local_settings.
import_local_settings()

# Fix crooked settings.
fix_up_databases(DATABASES)
