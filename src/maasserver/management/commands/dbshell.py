# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: start a database shell.

Overrides the default implementation.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = ['Command']

from django.core.management.commands import dbshell
from maasserver.testing.database import MAASClusterFixture


class Command(dbshell.Command):
    """Customized "dbshell" command."""

    def handle(self, **options):
        # Don't call up to Django's dbshell, because that ends up exec'ing the
        # shell, preventing this from clearing down the fixture.
        with MAASClusterFixture(options.get('database')) as cluster:
            cluster.shell(cluster.dbname)
