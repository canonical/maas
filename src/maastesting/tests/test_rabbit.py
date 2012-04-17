# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maastesting.rabbit`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.conf import settings
from maastesting.factory import factory
from maastesting.rabbit import RabbitServerSettings
from maastesting.testcase import TestCase
from rabbitfixture.server import RabbitServerResources


class TestRabbitServerSettings(TestCase):

    def test_patch(self):
        config = RabbitServerResources(
            hostname=factory.getRandomString(),
            port=factory.getRandomPort())
        self.useFixture(config)
        self.useFixture(RabbitServerSettings(config))
        self.assertEqual(
            "%s:%d" % (config.hostname, config.port),
            settings.RABBITMQ_HOST)
        self.assertEqual("guest", settings.RABBITMQ_PASSWORD)
        self.assertEqual("guest", settings.RABBITMQ_USERID)
        self.assertEqual("/", settings.RABBITMQ_VIRTUAL_HOST)
        self.assertTrue(settings.RABBITMQ_PUBLISH)
