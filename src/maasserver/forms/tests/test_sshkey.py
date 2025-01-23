# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `SSHKeyForm`."""


from django.http import HttpRequest

from maascommon.events import AUDIT
from maasserver.enum import ENDPOINT_CHOICES
from maasserver.forms import SSHKeyForm
from maasserver.models import Event
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestSSHKeyForm(MAASServerTestCase):
    """Tests for `SSHKeyForm`."""

    def test_creates_audit_event_on_save(self):
        user = factory.make_User()
        key_string = get_data("data/test_rsa0.pub")
        form = SSHKeyForm(user=user, data={"key": key_string})
        request = HttpRequest()
        request.user = user
        form.save(factory.pick_choice(ENDPOINT_CHOICES), request)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(event.description, "Created SSH key.")

    def test_creates_audit_event_for_specified_user_on_save(self):
        specified_user = factory.make_User()
        request_user = factory.make_User()
        key_string = get_data("data/test_rsa0.pub")
        form = SSHKeyForm(user=specified_user, data={"key": key_string})
        request = HttpRequest()
        request.user = request_user
        form.save(factory.pick_choice(ENDPOINT_CHOICES), request)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description, "Created SSH key for %s." % specified_user
        )
