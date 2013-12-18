# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Longpoll-related views tests."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from unittest import skip

from django.conf import settings
from maasserver import messages
from maasserver.exceptions import NoRabbit
from maasserver.testing.factory import factory
from maasserver.testing.rabbit import uses_rabbit_fixture
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.views.nodes import get_longpoll_context


class TestGetLongpollContext(MAASServerTestCase):

    def test_get_longpoll_context_empty_if_rabbitmq_publish_is_none(self):
        self.patch(settings, 'RABBITMQ_PUBLISH', None)
        messages.MESSAGING.reset()
        self.assertEqual({}, get_longpoll_context())

    def test_get_longpoll_context_returns_empty_if_rabbit_not_running(self):

        class FakeMessaging:
            """Fake :class:`RabbitMessaging`: fail with `NoRabbit`."""

            def getQueue(self, *args, **kwargs):
                raise NoRabbit("Pretending not to have a rabbit.")

        self.patch(messages.MESSAGING, '_cached_messaging', FakeMessaging())
        self.assertEqual({}, get_longpoll_context())

    def test_get_longpoll_context_empty_if_longpoll_url_is_None(self):
        self.patch(settings, 'LONGPOLL_PATH', None)
        messages.MESSAGING.reset()
        self.assertEqual({}, get_longpoll_context())

    @skip(
        "XXX: GavinPanella 2012-09-27 bug=1057250: Causes test "
        "failures in unrelated parts of the test suite.")
    @uses_rabbit_fixture
    def test_get_longpoll_context(self):
        longpoll = factory.getRandomString()
        self.patch(settings, 'LONGPOLL_PATH', longpoll)
        self.patch(settings, 'RABBITMQ_PUBLISH', True)
        messages.MESSAGING.reset()
        context = get_longpoll_context()
        self.assertItemsEqual(
            ['LONGPOLL_PATH', 'longpoll_queue'], context)
        self.assertEqual(longpoll, context['LONGPOLL_PATH'])
