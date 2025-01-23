# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest

from maascommon.events import AUDIT
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT_CHOICES
from maasserver.models import Event
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.events import EVENT_TYPES


class TestCreateAuditEvent(MAASServerTestCase):
    def test_create_audit_event_creates_audit_event_without_node(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        request.META = {"HTTP_HOST": factory.make_ipv4_address()}
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        create_audit_event(EVENT_TYPES.NODE_PXE_REQUEST, endpoint, request)
        event = Event.objects.get(node=None, type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(endpoint, event.endpoint)
        self.assertEqual("", event.user_agent)

    def test_create_audit_event_creates_audit_event_with_user_agent(self):
        node = factory.make_Node()
        request = HttpRequest()
        request.user = node.owner
        request.META = {
            "HTTP_USER_AGENT": factory.make_name("user_agent"),
            "HTTP_HOST": factory.make_ipv4_address(),
        }
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        create_audit_event(
            EVENT_TYPES.NODE_PXE_REQUEST,
            endpoint,
            request,
            system_id=node.system_id,
        )
        event = Event.objects.get(node=node, type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(request.headers["user-agent"], event.user_agent)

    def test_create_audit_event_creates_audit_event_with_description(self):
        node = factory.make_Node()
        request = HttpRequest()
        request.user = node.owner
        request.META = {
            "HTTP_USER_AGENT": factory.make_name("user_agent"),
            "HTTP_HOST": factory.make_ipv4_address(),
        }
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        description = factory.make_name("description")
        create_audit_event(
            EVENT_TYPES.NODE_PXE_REQUEST,
            endpoint,
            request,
            system_id=node.system_id,
            description=description,
        )
        event = Event.objects.get(node=node, type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(request.headers["user-agent"], event.user_agent)
        self.assertEqual(description, event.description)

    def test_create_audit_event_creates_audit_event_with_AnonymousUser(self):
        request = HttpRequest()
        request.user = AnonymousUser()
        request.META = {
            "HTTP_USER_AGENT": factory.make_name("user_agent"),
            "HTTP_HOST": factory.make_ipv4_address(),
        }
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        create_audit_event(EVENT_TYPES.NODE_PXE_REQUEST, endpoint, request)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertIsNone(event.user_id)

    def test_create_audit_event_creates_audit_event_with_empty_request(self):
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        create_audit_event(EVENT_TYPES.SETTINGS, endpoint)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertIsNone(event.ip_address)
        self.assertIsNone(event.user_id)
        self.assertEqual("", event.user_agent)
