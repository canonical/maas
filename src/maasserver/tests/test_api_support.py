# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for API helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from collections import namedtuple
import httplib

from django.core.urlresolvers import reverse
from maasserver.api_support import admin_method
from maasserver.models.config import (
    Config,
    ConfigManager,
    )
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from mock import (
    call,
    Mock,
    )


class TestOperationsResource(APITestCase):

    def test_type_error_is_not_hidden(self):
        # This tests that bug #1228205 is fixed (i.e. that a
        # TypeError is properly reported and not swallowed by
        # piston).

        # Create a valid configuration item.
        name = 'maas_name'
        value = factory.getRandomString()
        Config.objects.set_config(name, value)
        # Patch ConfigManager.get_config so that it will raise a
        # TypeError exception.
        self.patch(ConfigManager, "get_config", Mock(side_effect=TypeError))
        self.become_admin()
        response = self.client.get(
            reverse('maas_handler'),
            {
                'op': 'get_config',
                'name': name,
            })
        self.assertEqual(
            httplib.INTERNAL_SERVER_ERROR, response.status_code,
            response.content)


class TestAdminMethodDecorator(APITestCase):

    def test_non_admin_are_rejected(self):
        FakeRequest = namedtuple('FakeRequest', ['user'])
        request = FakeRequest(user=factory.make_user())
        mock = Mock()

        @admin_method
        def api_method(self, request):
            return mock()

        response = api_method('self', request)
        self.assertEqual(
            (httplib.FORBIDDEN, []),
            (response.status_code, mock.mock_calls))

    def test_admin_can_call_method(self):
        FakeRequest = namedtuple('FakeRequest', ['user'])
        request = FakeRequest(user=factory.make_admin())
        return_value = factory.make_name('return')
        mock = Mock(return_value=return_value)

        @admin_method
        def api_method(self, request):
            return mock()

        response = api_method('self', request)
        self.assertEqual(
            (return_value, [call()]),
            (response, mock.mock_calls))
