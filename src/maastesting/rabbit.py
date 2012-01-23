# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Helpers for testing with RabbitMQ."""

__metaclass__ = type
__all__ = [
    "RabbitServerResource",
    ]

from rabbitfixture.server import RabbitServer
from testresources import TestResource


class RabbitServerResource(TestResource):
    """A `TestResource` that wraps a `RabbitServer`.

    :ivar server: A `RabbitServer`.
    """

    def __init__(self, config=None):
        """See `TestResource.__init__`.

        :param config: An optional instance of
            `rabbitfixture.server.RabbitServerResources`.
        """
        super(RabbitServerResource, self).__init__()
        self.server = RabbitServer(config)

    def clean(self, resource):
        """See `TestResource.clean`."""
        resource.cleanUp()

    def make(self, dependency_resources):
        """See `TestResource.make`."""
        self.server.setUp()
        return self.server

    def isDirty(self):
        """See `TestResource.isDirty`.

        Always returns ``True`` because it's difficult to figure out if an
        `RabbitMQ` server has been used, and it will be very quick to reset
        once we have the management plugin.

        Also, somewhat confusingly, `testresources` uses `self._dirty` to
        figure out whether or not to recreate the resource in `self.reset`.
        That's only set by calling `self.dirtied`, which is fiddly from a
        test. For now we assume that it doesn't matter if it's dirty or not;
        tests need to ensure they're using uniquely named queues and/or
        exchanges, or explicity purge things during set-up.
        """
        return True

    def reset(self, old_resource, result=None):
        """See `TestResource.reset`."""
        # XXX: GavinPanella 2011-01-20 bug=???: When it becomes possible to
        # install rabbitmq-management on Precise this could be changed to
        # properly reset the running server.
        return super(RabbitServerResource, self).reset(old_resource, result)
