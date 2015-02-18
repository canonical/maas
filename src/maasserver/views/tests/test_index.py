# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver index view."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


import random

from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.views import index as index_module
from mock import MagicMock


class TestIndexView(MAASServerTestCase):

    def test__adds_port_number_to_context(self):
        self.client_log_in()
        port = random.randint(1024, 2048)
        fake = MagicMock()
        fake.endpoint.port = port
        mock_getServiceNamed = self.patch(
            index_module.services, "getServiceNamed")
        mock_getServiceNamed.return_value = fake
        response = self.client.get(reverse('index'))
        doc = fromstring(response.content)
        self.assertEquals(
            port, int(doc.head.find("base").get("data-websocket-port")))
