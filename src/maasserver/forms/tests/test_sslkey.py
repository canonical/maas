# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `SSLKeyForm`."""


from django.http import HttpRequest

from maascommon.events import AUDIT
from maasserver.enum import ENDPOINT_CHOICES
from maasserver.forms import SSLKeyForm
from maasserver.models import Event
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestSSLKeyForm(MAASServerTestCase):
    """Tests for `SSLKeyForm`."""

    def test_creates_audit_event_on_save(self):
        user = factory.make_User()
        key_string = get_data("data/test_x509_0.pem")
        form = SSLKeyForm(user=user, data={"key": key_string})
        request = HttpRequest()
        request.user = user
        form.save(factory.pick_choice(ENDPOINT_CHOICES), request)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Created SSL key.")
