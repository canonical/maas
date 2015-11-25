# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS Server application."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'DefaultMeta',
    'logger',
    ]

import logging
import os
import sys


logger = logging.getLogger("maasserver")


class DefaultMeta:
    """Base class for model `Meta` classes in the maasserver app.

    Each model in the models package outside of __init__.py needs a nested
    `Meta` class that defines `app_label`.  Otherwise, South won't recognize
    the model and will fail to generate schema migrations for it.
    """
    app_label = 'maasserver'


def execute_from_command_line():
    # When the "dbupgrade --south" command is performed we need to inject
    # django 1.6 to be used and south as an INSTALLED_APP before
    # django is ever imported. The dbupgrade parent command will set
    # 'DJANGO16_SOUTH_MODULES_PATH' in the environment.
    if 'DJANGO16_SOUTH_MODULES_PATH' in os.environ:
        # Inject django 1.6 and south path provided by the parent process.
        sys.path.insert(0, os.environ['DJANGO16_SOUTH_MODULES_PATH'])
        import django
        assert django.get_version() == "1.6.6"

        # Install south.
        from django.conf import settings
        settings.INSTALLED_APPS += (
            'south',
        )

    # Limit concurrency in all thread-pools to ONE.
    from maasserver.utils import threads
    threads.install_default_pool(maxthreads=1)
    threads.install_database_unpool(maxthreads=1)
    # Disable all database connections in the reactor.
    from maasserver.utils import orm
    from twisted.internet import reactor
    assert not reactor.running, "The reactor has been started too early."
    reactor.callFromThread(orm.disable_all_database_connections)

    # Hand over to Django.
    from django.core import management
    management.execute_from_command_line()


try:
    import maasfascist
    maasfascist  # Silence lint.
except ImportError:
    pass
