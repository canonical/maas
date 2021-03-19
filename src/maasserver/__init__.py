# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS Server application."""


import logging

from provisioningserver.utils.version import DISTRIBUTION

__version__ = DISTRIBUTION.version

default_app_config = "maasserver.apps.MAASConfig"

logger = logging.getLogger("maasserver")


class DefaultMeta:
    """Base class for model `Meta` classes in the maasserver app.

    Each model in the models package outside of __init__.py needs a nested
    `Meta` class that defines `app_label`.
    """

    app_label = "maasserver"


class DefaultViewMeta(DefaultMeta):
    """Default `Meta` class for a view-backed model."""

    managed = False


def execute_from_command_line():
    # Limit concurrency in all thread-pools to ONE.
    from maasserver.utils import threads

    threads.install_default_pool(maxthreads=1)
    threads.install_database_unpool(maxthreads=1)
    # Disable all database connections in the reactor.
    from twisted.internet import reactor

    from maasserver.utils import orm

    assert not reactor.running, "The reactor has been started too early."
    reactor.callFromThread(orm.disable_all_database_connections)
    # Configure logging; Django is no longer responsible for this. Behave as
    # if we're always at an interactive terminal (i.e. do not wrap stdout or
    # stderr with log machinery).
    from provisioningserver import logger

    logger.configure(mode=logger.LoggingMode.COMMAND)
    # Hand over to Django.
    from django.core import management

    management.execute_from_command_line()
