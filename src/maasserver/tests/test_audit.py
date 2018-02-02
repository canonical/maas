# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Audit logging utilities."""

__all__ = []

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from maasserver.audit import (
    create_audit_event,
    get_client_ip,
)
from maasserver.enum import ENDPOINT_CHOICES
from maasserver.models import (
    Event,
    EventType,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.events import (
    AUDIT,
    EVENT_TYPES,
)


class GetClientIPTest(MAASServerTestCase):

    def test__gets_client_ipv4_for_HTTP_X_FORWARDED_FOR(self):
        ip_address = factory.make_ipv4_address()
        request = HttpRequest()
        request.META = {
            'HTTP_X_FORWARDED_FOR': ip_address
            }
        self.assertEquals(ip_address, get_client_ip(request))

    def test__gets_client_ipv6_for_HTTP_X_FORWARDED_FOR(self):
        ip_address = factory.make_ipv6_address()
        request = HttpRequest()
        request.META = {
            'HTTP_X_FORWARDED_FOR': ip_address
            }
        self.assertEquals(ip_address, get_client_ip(request))

    def test__gets_client_ip_for_X_FORWARDED_FOR_with_proxies(self):
        ip_address = factory.make_ipv4_address()
        proxy1 = factory.make_ipv4_address()
        proxy2 = factory.make_ipv4_address()
        request = HttpRequest()
        request.META = {
            'HTTP_X_FORWARDED_FOR': "%s, %s, %s" % (
                ip_address, proxy1, proxy2),
            }
        self.assertEquals(ip_address, get_client_ip(request))

    def test__gets_client_ipv4_for_REMOTE_ADDR(self):
        ip_address = factory.make_ipv4_address()
        request = HttpRequest()
        request.META = {
            'REMOTE_ADDR': ip_address
            }
        self.assertEquals(ip_address, get_client_ip(request))

    def test__gets_client_ipv6_for_REMOTE_ADDR(self):
        ip_address = factory.make_ipv6_address()
        request = HttpRequest()
        request.META = {
            'REMOTE_ADDR': ip_address
            }
        self.assertEquals(ip_address, get_client_ip(request))

    def test__fallsback_to_REMOTE_ADDR_for_invalid_X_FORWARDED_FOR(self):
        ip_address = factory.make_ipv4_address()
        request = HttpRequest()
        request.META = {
            'HTTP_X_FORWARDED_FOR': factory.make_name('garbage ip'),
            'REMOTE_ADDR': ip_address,
            }
        self.assertEquals(ip_address, get_client_ip(request))

    def test__returns_None_for_invalid_ip(self):
        ip_address = factory.make_name('garbage ip')
        request = HttpRequest()
        request.META = {
            'REMOTE_ADDR': ip_address
            }
        self.assertIsNone(get_client_ip(request))


class CreateAuditEventTest(MAASServerTestCase):

    def test_create_audit_event_creates_audit_event_without_node(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        request.META = {
            'HTTP_HOST': factory.make_ipv4_address()
            }
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        create_audit_event(EVENT_TYPES.NODE_PXE_REQUEST, endpoint, request)
        event = Event.objects.get(node=None, user=user)
        self.assertIsNotNone(event)
        self.assertIsNotNone(EventType.objects.get(level=AUDIT))
        self.assertEquals(endpoint, event.endpoint)
        self.assertEquals('', event.user_agent)

    def test_create_audit_event_creates_audit_event_with_user_agent(self):
        node = factory.make_Node()
        request = HttpRequest()
        request.user = node.owner
        request.META = {
            'HTTP_USER_AGENT': factory.make_name('user_agent'),
            'HTTP_HOST': factory.make_ipv4_address(),
            }
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        create_audit_event(
            EVENT_TYPES.NODE_PXE_REQUEST, endpoint,
            request, system_id=node.system_id)
        event = Event.objects.get(node=node, user=node.owner)
        self.assertIsNotNone(event)
        self.assertIsNotNone(EventType.objects.get(level=AUDIT))
        self.assertEquals(request.META['HTTP_USER_AGENT'], event.user_agent)

    def test_create_audit_event_creates_audit_event_with_description(self):
        node = factory.make_Node()
        request = HttpRequest()
        request.user = node.owner
        request.META = {
            'HTTP_USER_AGENT': factory.make_name('user_agent'),
            'HTTP_HOST': factory.make_ipv4_address(),
            }
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        description = factory.make_name('description')
        create_audit_event(
            EVENT_TYPES.NODE_PXE_REQUEST, endpoint, request,
            system_id=node.system_id, description=description)
        event = Event.objects.get(node=node, user=node.owner)
        self.assertIsNotNone(event)
        self.assertIsNotNone(EventType.objects.get(level=AUDIT))
        self.assertEquals(request.META['HTTP_USER_AGENT'], event.user_agent)
        self.assertEquals(description, event.description)

    def test_create_audit_event_creates_audit_event_with_AnonymousUser(self):
        request = HttpRequest()
        request.user = AnonymousUser()
        request.META = {
            'HTTP_USER_AGENT': factory.make_name('user_agent'),
            'HTTP_HOST': factory.make_ipv4_address(),
            }
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        create_audit_event(EVENT_TYPES.NODE_PXE_REQUEST, endpoint, request)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertIsNotNone(EventType.objects.get(level=AUDIT))
        self.assertIsNone(event.user)
