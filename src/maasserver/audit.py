# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for Audit logging."""


from django.contrib.auth.models import AnonymousUser

from maascommon.events import AUDIT
from maasserver.models.event import Event
from maasserver.utils import get_remote_ip
from provisioningserver.events import EVENT_DETAILS


def create_audit_event(
    event_type, endpoint, request=None, system_id=None, description=None
):
    """Helper to register Audit events.

    These are events that have an event type level of AUDIT.
    """
    event_description = description or ""
    if request:
        user_agent = request.headers.get("user-agent", "")
        ip_address = get_remote_ip(request)
        user = (
            None if isinstance(request.user, AnonymousUser) else request.user
        )
    else:
        user_agent = ""
        ip_address = None
        user = None

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
