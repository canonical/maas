# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maastesting.rabbit`."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maastesting import TestCase
from maastesting.rabbit import RabbitServerResource
from rabbitfixture.server import RabbitServer


class TestRabbitServerResourceBasics(TestCase):

    def test_cycle(self):
        """
        A RabbitMQ server can be successfully brought up and shut-down.
        """
        resource = RabbitServerResource()
        server = resource.make({})
        try:
            self.assertIs(resource.server, server)
            self.assertIsInstance(server, RabbitServer)
        finally:
            resource.clean(server)

    def test_reset(self):
        """
        Resetting a RabbitMQ server resource when it has not explicitly been
        marked as dirty - via `RabbitServerResource.dirtied` - is a no-op; the
        same server is returned.
        """
        resource = RabbitServerResource()
        server = resource.make({})
        try:
            server2 = resource.reset(server)
            self.assertIs(server, server2)
        finally:
            resource.clean(server)


class TestRabbitServerResource(TestCase):

    resources = [
        ("rabbit", RabbitServerResource()),
        ]

    def test_one(self):
        """The `self.rabbit` resource is made available here."""
        self.assertIsInstance(self.rabbit, RabbitServer)

    def test_two(self):
        """The `self.rabbit resource is also made available here."""
        self.assertIsInstance(self.rabbit, RabbitServer)
