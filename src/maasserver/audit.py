# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for Audit logging."""

__all__ = []

from django.contrib.auth.models import AnonymousUser
from maasserver.models.event import Event
from netaddr import (
    valid_ipv4,
    valid_ipv6,
)
from provisioningserver.events import (
    AUDIT,
    EVENT_DETAILS,
)


def is_valid_ip(ip):
    """Check the validity of an IP address."""
    return valid_ipv4(ip) or valid_ipv6(ip)


def get_client_ip(request):
    """Get the client IP address."""
    # Try to obtain IP Address from X-Forwarded-For first.
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
        if is_valid_ip(ip):
            return ip
    # Fallback to REMOTE_ADDR second.
    ip = request.META.get('REMOTE_ADDR')

    return ip if is_valid_ip(ip) else None


def create_audit_event(
        event_type, endpoint, request, system_id=None, description=None):
    """Helper to register Audit events.

    These are events that have an event type level of AUDIT."""
    event_description = description if description is not None else ''
    # Retrieve Django request's user agent if it is set.
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    ip_address = get_client_ip(request)
    user = None if isinstance(request.user, AnonymousUser) else request.user

    Event.objects.register_event_and_event_type(
        type_name=event_type,
        type_description=EVENT_DETAILS[event_type].description,
        type_level=AUDIT, event_description=event_description,
        system_id=system_id, user=user, ip_address=ip_address,
        endpoint=endpoint, user_agent=user_agent)
