# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import urllib.error
import urllib.parse
import urllib.request

from django.urls import reverse
from formencode.validators import Int

from maascommon.events import AUDIT
from maasserver.api.nodes import filtered_nodes_list_from_request
from maasserver.api.support import operation, OperationsHandler
from maasserver.api.utils import get_optional_param, get_overridden_query_dict
from maasserver.enum import NODE_TYPE
from maasserver.exceptions import MAASAPIBadRequest
from maasserver.models import Event
from maasserver.models.eventtype import LOGGING_LEVELS, LOGGING_LEVELS_BY_NAME

MAX_EVENT_LOG_COUNT = 1000
DEFAULT_EVENT_LOG_LIMIT = 100
DATETIME_FORMAT = "%a, %d %b. %Y %H:%M:%S"


def event_to_dict(event):
    """Convert `Event` to a dictionary."""
    return dict(
        username=(event.owner),
        node=(event.node.system_id if event.node is not None else None),
        hostname=(event.hostname),
        id=event.id,
        level=event.type.level_str,
        created=event.created.strftime(DATETIME_FORMAT),
        type=event.type.description,
        description=(
            event.render_audit_description
            if event.type.level == AUDIT
            else event.description
        ),
    )


class EventsHandler(OperationsHandler):
    """
    Retrieve filtered node events.

    A specific Node's events is identified by specifying one or more
    ids, hostnames, or mac addresses as a list.
    """

    api_doc_section_name = "Events"

    create = read = update = delete = None

    model = Event

    all_params = frozenset(
        (
            "agent_name",
            "domain",
            "hostname",
            "id",  # system_id.
            "level",
            "limit",
            "mac_address",
            "op",
            "zone",
            "owner",
        )
    )

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("events_handler", [])

    @operation(idempotent=True)
    def query(self, request):
        """@description-title List node events
        @description List node events, optionally filtered by various criteria
        via URL query parameters.

        @param (string) "hostname" [required=false] An optional hostname. Only
        events relating to the node with the matching hostname will be
        returned. This can be specified multiple times to get events relating
        to more than one node.

        @param (string) "mac_address" [required=false] An optional list of MAC
        addresses.  Only nodes with matching MAC addresses will be returned.

        @param (string) "id" [required=false] An optional list of system ids.
        Only nodes with matching system ids will be returned.

        @param (string) "zone" [required=false] An optional name for a physical
        zone. Only nodes in the zone will be returned.

        @param (string) "agent_name" [required=false] An optional agent name.
        Only nodes with matching agent names will be returned.

        @param (string) "level" [required=false] Desired minimum log level of
        returned events. Returns this level of events and greater. Choose from:
        %(log_levels)s.  The default is INFO.

        @param (string) "limit" [required=false] Optional number of events to
        return. Default 100.  Maximum: 1000.

        @param (string) "before" [required=false] Optional event id.  Defines
        where to start returning older events.

        @param (string) "after" [required=false] Optional event id.  Defines
        where to start returning newer events.

        @param (string) "owner" [required=false] If specified, filters the list
        to show only events owned by the specified username.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        events objects.
        @success-example "success-json" [exkey=events-query] placeholder text
        """
        # Extract & validate optional parameters from the request.
        after = get_optional_param(request.GET, "after", None, Int)
        before = get_optional_param(request.GET, "before", None, Int)
        level = get_optional_param(request.GET, "level", "INFO")
        limit = get_optional_param(
            request.GET, "limit", DEFAULT_EVENT_LOG_LIMIT, Int
        )
        owner = get_optional_param(request.GET, "owner", default=None)

        # Limit what we'll return to avoid being swamped.
        if limit > MAX_EVENT_LOG_COUNT:
            raise MAASAPIBadRequest(
                ("Requested number of events %d is greater than limit: %d")
                % (limit, MAX_EVENT_LOG_COUNT)
            )
        else:
            # The limit should never be less than 1.
            limit = 1 if limit < 1 else limit

        # Filter first by optional node ID, hostname, MAC, etc.
        nodes = filtered_nodes_list_from_request(request)
        # Event lists aren't supported on devices.
        nodes = nodes.exclude(node_type=NODE_TYPE.DEVICE)

        # Check first for AUDIT level.
        if level == LOGGING_LEVELS[AUDIT]:
            events = Event.objects.filter(type__level=AUDIT, node__in=nodes)
        elif level in LOGGING_LEVELS_BY_NAME:
            events = Event.objects.filter(node__in=nodes)
            # Eliminate logs below the requested level.
            events = events.exclude(
                type__level__lt=LOGGING_LEVELS_BY_NAME[level]
            )
        elif level is not None:
            raise MAASAPIBadRequest("Unrecognised log level: %s" % level)

        events = events.all().select_related("type").select_related("node")

        # Filter events for owner.
        if owner is not None:
            events = events.filter(username=owner)

        # Future feature:
        # This is where we would filter for events 'since last node deployment'
        # using a query param like since_last_deployed=true, but we aren't
        # right now because we don't currently record a timestamp of the last
        # deployment, and we don't have an event subtype for node status
        # changes to filter for the deploying status event.

        if after is None and before is None:
            # Get `limit` events, newest first.
            events = events.order_by("-id")
            events = events[:limit]
        elif after is None:
            # Get `limit` events, newest first, all before `before`.
            events = events.filter(id__lt=before)
            events = events.order_by("-id")
            events = events[:limit]
        elif before is None:
            # Get `limit` events, OLDEST first, all after `after`, then
            # reverse the results.
            events = events.filter(id__gt=after)
            events = events.order_by("id")
            events = reversed(events[:limit])
        else:
            raise MAASAPIBadRequest(
                "There is undetermined behaviour when both "
                "`after` and `before` are specified."
            )

        # We need to load all of these events at some point, so save them
        # into a list now so that len() is cheap.
        events = list(events)

        # Helper for building prev_uri and next_uri.
        def make_uri(params, base=reverse("events_handler")):  # noqa: B008
            query = urllib.parse.urlencode(params, doseq=True)
            url = urllib.parse.urlparse(base)._replace(query=query)
            return url.geturl()

        # Figure out a URI to obtain a set of newer events.
        next_uri_params = get_overridden_query_dict(
            request.GET, {"before": []}, self.all_params
        )
        if len(events) == 0:
            if before is None:
                # There are no newer events NOW, but there may be later.
                next_uri = make_uri(next_uri_params)
            else:
                # Without limiting to `before`, we might find some more events.
                next_uri_params["after"] = before - 1
                next_uri = make_uri(next_uri_params)
        else:
            # The first event is the newest.
            next_uri_params["after"] = str(events[0].id)
            next_uri = make_uri(next_uri_params)

        # Figure out a URI to obtain a set of older events.
        prev_uri_params = get_overridden_query_dict(
            request.GET, {"after": []}, self.all_params
        )
        if len(events) == 0:
            if after is None:
                # There are no older events and never will be.
                prev_uri = None
            else:
                # Without limiting to `after`, we might find some more events.
                prev_uri_params["before"] = after + 1
                prev_uri = make_uri(prev_uri_params)
        else:
            # The last event is the oldest.
            prev_uri_params["before"] = str(events[-1].id)
            prev_uri = make_uri(prev_uri_params)

        return {
            "count": len(events),
            "events": [event_to_dict(event) for event in events],
            "next_uri": next_uri,
            "prev_uri": prev_uri,
        }

    query.__doc__ %= {"log_levels": ", ".join(sorted(LOGGING_LEVELS_BY_NAME))}
