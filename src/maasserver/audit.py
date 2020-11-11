# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for Audit logging."""


from django.contrib.auth.models import AnonymousUser

from maasserver.models.event import Event
from maasserver.utils import get_remote_ip
from provisioningserver.events import AUDIT, EVENT_DETAILS


def create_audit_event(
    event_type, endpoint, request, system_id=None, description=None
):
    """Helper to register Audit events.

    These are events that have an event type level of AUDIT."""
    event_description = description if description is not None else ""
    # Retrieve Django request's user agent if it is set.
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    ip_address = get_remote_ip(request)
    user = None if isinstance(request.user, AnonymousUser) else request.user

    Event.objects.register_event_and_event_type(
        type_name=event_type,
        type_description=EVENT_DETAILS[event_type].description,
        type_level=AUDIT,
        event_description=event_description,
        system_id=system_id,
        user=user,
        ip_address=ip_address,
        endpoint=endpoint,
        user_agent=user_agent,
    )
