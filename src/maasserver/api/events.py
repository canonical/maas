# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "EventsHandler",
]

import urllib.error
import urllib.parse
import urllib.request

from django.core.urlresolvers import reverse
from formencode.validators import Int
from maasserver.api.nodes import filtered_nodes_list_from_request
from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.api.utils import (
    get_optional_param,
    get_overridden_query_dict,
)
from maasserver.enum import NODE_TYPE
from maasserver.exceptions import MAASAPIBadRequest
from maasserver.models import Event
from maasserver.models.eventtype import LOGGING_LEVELS_BY_NAME


MAX_EVENT_LOG_COUNT = 1000
DEFAULT_EVENT_LOG_LIMIT = 100


def event_to_dict(event):
    """Convert `Event` to a dictionary."""
    return dict(
        node=event.node.system_id,
        hostname=event.node.hostname,
        id=event.id,
        level=event.type.level_str,
        created=event.created.strftime('%a, %d %b. %Y %H:%M:%S'),
        type=event.type.description,
        description=event.description
    )


class EventsHandler(OperationsHandler):
    """Retrieve filtered node events.

    A specific Node's events is identified by specifying one or more
    ids, hostnames, or mac addresses as a list.
    """

    api_doc_section_name = "Events"

    create = read = update = delete = None

    model = Event

    all_params = (
        'after',
        'agent_name',
        'id',
        'level',
        'limit',
        'mac_address',
        'op',
        'zone')

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('events_handler', [])

    @operation(idempotent=True)
    def query(self, request):
        """List Node events, optionally filtered by various criteria via
        URL query parameters.

        :param hostname: An optional hostname. Only events relating to the node
            with the matching hostname will be returned. This can be specified
            multiple times to get events relating to more than one node.
        :param mac_address: An optional list of MAC addresses.  Only
            nodes with matching MAC addresses will be returned.
        :param id: An optional list of system ids.  Only nodes with
            matching system ids will be returned.
        :param zone: An optional name for a physical zone. Only nodes in the
            zone will be returned.
        :param agent_name: An optional agent name.  Only nodes with
            matching agent names will be returned.
        :param level: Desired minimum log level of returned events. Returns
            this level of events and greater. Choose from: %(log_levels)s.
            The default is INFO.
        :param limit: Optional number of events to return. Default 100.
            Maximum: 1000.
        :param before: Optional event id.  Defines where to start returning
            older events.
        :param after: Optional event id.  Defines where to start returning
            newer events.
        """
        # Filter first by optional node ID, hostname, MAC, etc.
        nodes = filtered_nodes_list_from_request(request)
        # Event lists aren't supported on devices.
        nodes = nodes.exclude(node_type=NODE_TYPE.DEVICE)

        # Extract & validate optional parameters from the request.
        after = get_optional_param(request.GET, 'after', None, Int)
        before = get_optional_param(request.GET, 'before', None, Int)
        level = get_optional_param(request.GET, 'level', 'INFO')
        limit = get_optional_param(
            request.GET, "limit", DEFAULT_EVENT_LOG_LIMIT, Int)

        # Limit what we'll return to avoid being swamped.
        if limit > MAX_EVENT_LOG_COUNT:
            raise MAASAPIBadRequest((
                "Requested number of events %d is greater than"
                " limit: %d") % (limit, MAX_EVENT_LOG_COUNT))
        else:
            # The limit should never be less than 1.
            limit = 1 if limit < 1 else limit

        # Begin constructing the query.
        node_events = Event.objects.filter(node=nodes)

        # Eliminate logs below the requested level.
        if level in LOGGING_LEVELS_BY_NAME:
            node_events = node_events.exclude(
                type__level__lt=LOGGING_LEVELS_BY_NAME[level])
        elif level is not None:
            raise MAASAPIBadRequest(
                "Unrecognised log level: %s" % level)

        # Future feature:
        # This is where we would filter for events 'since last node deployment'
        # using a query param like since_last_deployed=true, but we aren't
        # right now because we don't currently record a timestamp of the last
        # deployment, and we don't have an event subtype for node status
        # changes to filter for the deploying status event.

        node_events = (
            node_events.all()
            .prefetch_related('type')
            .prefetch_related('node'))

        if after is None and before is None:
            # Get `limit` events, newest first.
            node_events = node_events.order_by('-id')
            node_events = node_events[:limit]
        elif after is None:
            # Get `limit` events, newest first, all before `before`.
            node_events = node_events.filter(id__lt=before)
            node_events = node_events.order_by('-id')
            node_events = node_events[:limit]
        elif before is None:
            # Get `limit` events, OLDEST first, all after `after`, then
            # reverse the results.
            node_events = node_events.filter(id__gt=after)
            node_events = node_events.order_by('id')
            node_events = reversed(node_events[:limit])
        else:
            raise MAASAPIBadRequest(
                "There is undetermined behaviour when both "
                "`after` and `before` are specified.")

        # We need to load all of these events at some point, so save them
        # into a list now so that len() is cheap.
        node_events = list(node_events)

        # Helper for building prev_uri and next_uri.
        def make_uri(params, base=reverse('events_handler')):
            query = urllib.parse.urlencode(params, doseq=True)
            url = urllib.parse.urlparse(base)._replace(query=query)
            return url.geturl()

        # Figure out a URI to obtain a set of newer events.
        next_uri_params = get_overridden_query_dict(
            request.GET, {"before": []}, self.all_params)
        if len(node_events) == 0:
            if before is None:
                # There are no newer events NOW, but there may be later.
                next_uri = make_uri(next_uri_params)
            else:
                # Without limiting to `before`, we might find some more events.
                next_uri_params["after"] = before - 1
                next_uri = make_uri(next_uri_params)
        else:
            # The first event is the newest.
            next_uri_params["after"] = str(node_events[0].id)
            next_uri = make_uri(next_uri_params)

        # Figure out a URI to obtain a set of older events.
        prev_uri_params = get_overridden_query_dict(
            request.GET, {"after": []}, self.all_params)
        if len(node_events) == 0:
            if after is None:
                # There are no older events and never will be.
                prev_uri = None
            else:
                # Without limiting to `after`, we might find some more events.
                prev_uri_params["before"] = after + 1
                prev_uri = make_uri(prev_uri_params)
        else:
            # The last event is the oldest.
            prev_uri_params["before"] = str(node_events[-1].id)
            prev_uri = make_uri(prev_uri_params)

        return {
            "count": len(node_events),
            "events": [event_to_dict(event) for event in node_events],
            "next_uri": next_uri,
            "prev_uri": prev_uri,
        }

    query.__doc__ %= {"log_levels": ", ".join(sorted(LOGGING_LEVELS_BY_NAME))}
