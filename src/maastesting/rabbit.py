# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for testing with RabbitMQ."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "get_rabbit",
    "RabbitServerSettings",
    "start_rabbit",
    "stop_rabbit",
    "use_rabbit_fixture",
    "uses_rabbit_fixture",
    ]

from functools import wraps

from fixtures import Fixture
from rabbitfixture.server import RabbitServer
from testtools.monkey import MonkeyPatcher


class RabbitServerSettings(Fixture):
    """
    This patches the active Django settings to point the application at the
    ephemeral RabbitMQ server specified by the given configuration.
    """

    def __init__(self, config):
        super(RabbitServerSettings, self).__init__()
        self.config = config

    def setUp(self):
        super(RabbitServerSettings, self).setUp()
        from django.conf import settings
        patcher = MonkeyPatcher()
        patcher.add_patch(
            settings, "RABBITMQ_HOST",
            "%s:%d" % (self.config.hostname, self.config.port))
        patcher.add_patch(settings, "RABBITMQ_USERID", "guest")
        patcher.add_patch(settings, "RABBITMQ_PASSWORD", "guest")
        patcher.add_patch(settings, "RABBITMQ_VIRTUAL_HOST", "/")
        patcher.add_patch(settings, "RABBITMQ_PUBLISH", True)
        self.addCleanup(patcher.restore)
        patcher.patch()


# See {start,stop,get}_rabbit().
rabbit = None


def start_rabbit():
    """Start a shared :class:`RabbitServer`."""
    global rabbit
    if rabbit is None:
        rabbit = RabbitServer()
        rabbit.setUp()


def stop_rabbit():
    """Stop a shared :class:`RabbitServer`, if any."""
    global rabbit
    if rabbit is not None:
        rabbit.cleanUp()
        rabbit = None


def get_rabbit():
    """Start and return a shared :class:`RabbitServer`."""
    global rabbit
    start_rabbit()
    return rabbit


def use_rabbit_fixture(test):
    """Ensure that a :class:`RabbitServer` is started, and Django's setting
    updated to point to it, and that Django's settings are returned to their
    original values at the end.
    """
    config = get_rabbit().config
    fixture = RabbitServerSettings(config)
    test.useFixture(fixture)


def uses_rabbit_fixture(func):
    """Decorate a test function with `use_rabbit_fixture`."""
    @wraps(func)
    def wrapper(self):
        use_rabbit_fixture(self)
        return func(self)
    return wrapper
