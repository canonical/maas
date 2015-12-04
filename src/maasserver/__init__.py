# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS Server application."""

__all__ = [
    'DefaultMeta',
    'logger',
    ]

import logging


logger = logging.getLogger("maasserver")


class DefaultMeta:
    """Base class for model `Meta` classes in the maasserver app.

    Each model in the models package outside of __init__.py needs a nested
    `Meta` class that defines `app_label`.  Otherwise, South won't recognize
    the model and will fail to generate schema migrations for it.
    """
    app_label = 'maasserver'


def execute_from_command_line():
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
