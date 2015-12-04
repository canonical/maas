# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "EventsHandler",
]

import logging
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
        """

        # Filter first by optional node id, hostname, or mac
        nodes = filtered_nodes_list_from_request(request)
        limit = get_optional_param(
            request.GET, "limit", DEFAULT_EVENT_LOG_LIMIT, Int)

        start_event_id_param = get_optional_param(
            request.GET, 'after', None, Int)

        log_level = get_optional_param(request.GET, 'level', 'INFO')

        if limit > MAX_EVENT_LOG_COUNT:
            raise MAASAPIBadRequest((
                "Requested number of events %d is greater than"
                " limit: %d") % (limit, MAX_EVENT_LOG_COUNT))

        if start_event_id_param is not None:
            node_events = Event.objects.filter(
                id__gte=start_event_id_param,
                node=nodes)
            start_event_id = start_event_id_param
        else:
            node_events = Event.objects.filter(node=nodes)
            start_event_id = 0

        # Filter next by log level >= to 'level', if specified
        if log_level is None and log_level != 'NOTSET':
            numeric_log_level = logging.NOTSET
        elif log_level in LOGGING_LEVELS_BY_NAME:
            numeric_log_level = LOGGING_LEVELS_BY_NAME[log_level]
            assert isinstance(numeric_log_level, int)
        else:
            raise MAASAPIBadRequest(
                "Unknown log level: %s" % log_level)

        if log_level is not None and log_level != 'NOTSET':
            node_events = node_events.exclude(
                type__level__lt=numeric_log_level)

        # Future feature:
        # This is where we would filter for events 'since last node deployment'
        # using a query param like since_last_deployed=true, but we aren't
        # right now because we don't currently record a timestamp of the last
        # deployment, and we don't have an event subtype for node status
        # changes to filter for the deploying status event.

        base_path = reverse('events_handler')

        prev_uri_params = get_overridden_query_dict(
            request.GET,
            {'after': max(0, start_event_id - limit)}, self.all_params)
        prev_uri = '%s?%s' % (base_path,
                              urllib.parse.urlencode(
                                  prev_uri_params,
                                  doseq=True))

        next_uri_params = get_overridden_query_dict(
            request.GET,
            {'after': start_event_id + limit}, self.all_params)
        next_uri = '%s?%s' % (base_path,
                              urllib.parse.urlencode(
                                  next_uri_params,
                                  doseq=True))

        node_events = (
            node_events.all().order_by('id')
            .prefetch_related('type')
            .prefetch_related('node'))

        # Lastly, order by id and return up to 'limit' events
        if start_event_id_param is not None:
            # If start_event_id is specified, limit to a window of
            # 'limit' events with 'start_event_id' being the id
            # of the oldest event
            node_events = node_events.order_by('id')
            node_events = reversed(node_events[:limit])
        else:
            # If start_event_id is not specified, limit to most recent
            # 'limit' events
            node_events = node_events.order_by('-id')
            node_events = node_events[:limit]

        # We need to load all of these events at some point, so save them
        # into a list now so that len() is cheap.
        node_events = list(node_events)

        displayed_events_count = len(node_events)
        events_dict = dict(
            count=displayed_events_count,
            events=[event_to_dict(event) for event in node_events],
            next_uri=next_uri,
            prev_uri=prev_uri,
        )
        return events_dict

    query.__doc__ %= {"log_levels": ", ".join(LOGGING_LEVELS_BY_NAME)}
