# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Customisation of Django test database setup."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'patch_db_creation',
    ]

import os.path

import django.db.backends.postgresql_psycopg2.creation as backend_creation
from provisioningserver.utils.shell import call_and_check


def patch_db_creation(dev_root):
    """Patch Django's creation of PostgreSQL test databases.

    This injects just one customisation: right after creating the database,
    but before running any migrations, apply the baseline schema that's stored
    in the MAAS branch as an SQL input file.  This is much faster than running
    the migrations.

    South will notice which migrations have been applied, and just runs the
    ones that are still missing from the baseline schema.

    :param dev_root: The development root directory, i.e. the branch where
        MAAS is being run.
    """
    original_create = backend_creation.DatabaseCreation._create_test_db

    def patched_create(self, *args, **kwargs):
        """Patch for injection into Django's postgres/psycopg2 backend.

        THIS IS A FILTHY HACK.  It may break with Django upgrades, in which
        case, feel free to disable it until it can be fixed.  It's only here
        to speed up test runs.

        Disable the hack by commenting out the call to `patch_db_creation`
        in the applicable settings module.
        """
        result = original_create(self, *args, **kwargs)
        baseline_dump = os.path.join(dev_root, 'schema', 'baseline.sql')
        if os.path.exists(baseline_dump):
            # Load the baseline schema.
            #
            # The --host option may look strange: we connect to the database
            # on a Unix domain socket, and the postgres clients accept an
            # absolute path to a socket on the filesystem in the place of a
            # host name to connect to.
            call_and_check([
                'psql',
                '--host=%s' % os.path.join(dev_root, 'db'),
                '--dbname=%s' % self._get_test_db_name(),
                '--file=%s' % baseline_dump,
                ])
        return result

    backend_creation.DatabaseCreation._create_test_db = patched_create
