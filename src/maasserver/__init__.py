# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS Server application."""

__all__ = [
    'DefaultMeta',
    'is_master_process',
    'logger',
    ]

import logging
from os import environ

from provisioningserver.monkey import add_patches_to_twisted


logger = logging.getLogger("maasserver")


class DefaultMeta:
    """Base class for model `Meta` classes in the maasserver app.

    Each model in the models package outside of __init__.py needs a nested
    `Meta` class that defines `app_label`.  Otherwise, South won't recognize
    the model and will fail to generate schema migrations for it.
    """
    app_label = 'maasserver'


def is_master_process():
    """Return True if this is the master process for the region controller.

    The region controller starts 4 regiond processes the first regiond
    process is started as the master. The master runs more services
    than the other regiond processes, services that only require to be ran
    on one regiond per region controller.
    """
    worker_id = environ.get("MAAS_REGIOND_WORKER_ID")
    if worker_id is None:
        return False
    else:
        return int(worker_id) == 1


def execute_from_command_line():
    # Make Twisted IPv6 ready, at least for MAAS's needs.
    add_patches_to_twisted()
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
