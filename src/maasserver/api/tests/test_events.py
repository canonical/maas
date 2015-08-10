# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the events API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = []

import httplib
from itertools import combinations
import json
import logging
import random
from random import randint
from urlparse import (
    parse_qsl,
    urlparse,
)

from django.core.urlresolvers import reverse
from maasserver.api import events as events_module
from maasserver.api.tests.test_nodes import RequestFixture
from maasserver.models.eventtype import LOGGING_LEVELS
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils import ignore_unused
from maastesting.djangotestcase import count_queries
from testtools.matchers import (
    Contains,
    Equals,
    MatchesListwise,
)


def extract_event_desc(parsed_result):
    """List the system_ids of the nodes in `parsed_result`'s events."""
    return [event.get('description') for event in parsed_result['events']]


def extract_event_ids(parsed_result):
    """List the system_ids of the nodes in `parsed_result`'s events."""
    return [event.get('id') for event in parsed_result['events']]


def make_events_with_log_levels(log_levels_dict, events_per_level=2):
    return [factory.make_Event(
        type=factory.make_EventType(
            level=level[1])).id
            for level in log_levels_dict
            for _ in range(events_per_level)
            ]


class TestEventsAPI(APITestCase):
    """Tests for /api/1.0/events/."""
    log_levels = (('CRITICAL', logging.CRITICAL),
                  ('ERROR', logging.ERROR),
                  ('WARNING', logging.WARNING),
                  ('INFO', logging.INFO),
                  ('DEBUG', logging.DEBUG),
                  )

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/events/', reverse('events_handler'))

    def create_nodes_in_group_with_events(
            self, nodegroup, number_nodes=2, number_events=2):
        for _ in range(number_nodes):
            node = factory.make_Node(nodegroup=nodegroup, mac=True)
            for _ in range(number_events):
                factory.make_Event(node=node)

    def test_GET_query_without_events_returns_empty_list(self):
        # If there are no nodes to list, the "list" op still works but
        # returns an empty list.
        response = self.client.get(
            reverse('events_handler'), {
                'op': 'query'})

        self.assertItemsEqual(
            {'count': 0,
             'events': [],
             'prev_uri': '',
             'next_uri': ''},
            json.loads(response.content))

    def test_GET_query_orders_by_reverse_id(self):
        # Events are returned in reverse id order (newest first).
        node = factory.make_Node()
        event_ids = [factory.make_Event(node=node).id for _ in range(3)]
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'level': 'DEBUG'}
        )
        parsed_result = json.loads(response.content)
        self.assertSequenceEqual(
            list(reversed(event_ids)), extract_event_ids(parsed_result))
        self.assertEqual(parsed_result['count'], len(event_ids))

    def test_GET_query_with_id_returns_matching_nodes(self):
        # The "list" operation takes optional "id" parameters.  Only
        # events from nodes with matching ids will be returned.
        nodes = [factory.make_Node() for _ in range(3)]
        ids = [node.system_id for node in nodes]
        events = [factory.make_Event(node=node) for node in nodes]
        matching_id = ids[0]
        matching_events = events[0].id
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'id': [matching_id],
            'level': 'DEBUG'
        })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [matching_events], extract_event_ids(parsed_result))
        self.assertEqual(parsed_result['count'], len([matching_events]))

    def test_GET_query_with_nonexistent_id_returns_empty_list(self):
        # Trying to list events for a nonexistent node id returns a list
        # containing no nodes -- even if other (non-matching) nodes exist.
        node = factory.make_Node()
        [factory.make_Event(node=node) for _ in range(3)]
        existing_id = node.system_id
        nonexistent_id = existing_id + factory.make_string()
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'id': [nonexistent_id],
        })
        self.assertItemsEqual({'count': 0,
                               'events': [],
                               'prev_uri': '',
                               'next_uri': ''},
                              json.loads(response.content))

    def test_GET_query_with_ids_orders_by_id_reverse(self):
        # Even when node ids are passed to "list," events for nodes are
        # returned in event id order, not necessarily in the order of the
        # node id arguments.
        nodes = [factory.make_Node() for _ in range(3)]
        ids = [node.system_id for node in nodes]
        events = [factory.make_Event(node=node) for node in nodes]
        event_ids = [event.id for event in reversed(events)]
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'id': list(reversed(ids)),
            'level': 'DEBUG'
        })
        parsed_result = json.loads(response.content)
        self.assertSequenceEqual(
            event_ids, extract_event_ids(parsed_result))
        self.assertEqual(parsed_result['count'], len(event_ids))
        self.assertNumQueries(1)

    def test_GET_query_with_some_matching_ids_returns_matching_nodes(self):
        # If some nodes match the requested ids and some don't, only the
        # events matching nodes specified are returned.
        existing_node = factory.make_Node()
        existing_id = existing_node.system_id
        existing_event_ids = [
            factory.make_Event(
                node=existing_node).id for _ in range(3)]
        nonexistent_id = existing_id + factory.make_string()
        # Generate some non-matching events as well
        [factory.make_Event().id for counter in range(3)]
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'id': [existing_id, nonexistent_id],
            'level': 'DEBUG'
        })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            reversed(existing_event_ids), extract_event_ids(parsed_result))
        self.assertEqual(parsed_result['count'], len(existing_event_ids))

    def test_GET_query_with_hostname_returns_matching_nodes(self):
        # The list operation takes optional "hostname" parameters. Only events
        # for nodes with matching hostnames will be returned.
        nodes = [factory.make_Node() for _ in range(3)]
        events = [factory.make_Event(node=node) for node in nodes]

        matching_hostname = nodes[0].hostname
        matching_event_id = events[0].id
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'hostname': [matching_hostname],
            'level': 'DEBUG'
        })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [matching_event_id], extract_event_ids(parsed_result))
        self.assertEqual(parsed_result['count'], len([matching_event_id]))

    def test_GET_query_with_macs_returns_matching_nodes(self):
        # The "list" operation takes optional "mac_address" parameters. Only
        # events for nodes with matching MAC addresses will be returned.
        macs = [factory.make_MACAddress_with_Node() for _ in range(3)]
        events = [factory.make_Event(node=mac.node) for mac in macs]
        matching_mac = macs[0].mac_address
        matching_event_id = events[0].id
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'mac_address': [matching_mac],
            'level': 'DEBUG'
        })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [matching_event_id], extract_event_ids(parsed_result))
        self.assertEqual(parsed_result['count'], len([matching_event_id]))

    def test_GET_query_with_invalid_macs_returns_sensible_error(self):
        # If specifying an invalid MAC, make sure the error that's
        # returned is not a crazy stack trace, but something nice to
        # humans.
        bad_mac1 = '00:E0:81:DD:D1:ZZ'  # ZZ is bad.
        bad_mac2 = '00:E0:81:DD:D1:XX'  # XX is bad.
        ok_mac = factory.make_MACAddress_with_Node()
        [factory.make_Event(node=ok_mac.node) for _ in range(3)]
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'mac_address': [bad_mac1, bad_mac2, ok_mac],
            'level': 'DEBUG'
        })
        observed = response.status_code, response.content
        expected = (
            Equals(httplib.BAD_REQUEST),
            Contains(
                "Invalid MAC address(es): 00:E0:81:DD:D1:ZZ, "
                "00:E0:81:DD:D1:XX"),
        )
        self.assertThat(observed, MatchesListwise(expected))

    def test_GET_query_with_agent_name_filters_by_agent_name(self):
        non_listed_node = factory.make_Node(
            agent_name=factory.make_name('agent_name'))
        ignore_unused(non_listed_node)
        agent_name = factory.make_name('agent-name')
        node = factory.make_Node(agent_name=agent_name)

        [factory.make_Event(node=non_listed_node) for _ in range(3)]
        matching_event_ids = [
            factory.make_Event(
                node=node).id for _ in range(3)]

        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'agent_name': agent_name,
            'level': 'DEBUG',
        })

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)

        matching_event_ids = list(reversed(matching_event_ids))
        self.assertSequenceEqual(
            matching_event_ids, extract_event_ids(parsed_result))
        self.assertEqual(parsed_result['count'], len(matching_event_ids))

    def test_GET_query_with_agent_name_filters_with_empty_string(self):
        non_listed_node = factory.make_Node(
            agent_name=factory.make_name('agent-name'))
        node = factory.make_Node(agent_name='')

        [factory.make_Event(node=non_listed_node) for _ in range(3)]
        matching_event_ids = [
            factory.make_Event(
                node=node).id for _ in range(3)]

        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'agent_name': '',
            'level': 'DEBUG'
        })
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        matching_event_ids = list(reversed(matching_event_ids))
        self.assertSequenceEqual(
            matching_event_ids, extract_event_ids(parsed_result))
        self.assertEqual(parsed_result['count'], len(matching_event_ids))

    def test_GET_query_without_agent_name_does_not_filter(self):
        nodes = [
            factory.make_Node(agent_name=factory.make_name('agent-name'))
            for _ in range(3)]
        matching_event_ids = [
            factory.make_Event(
                node=node).id for node in nodes]
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'level': 'DEBUG'
        }
        )
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        matching_event_ids = list(reversed(matching_event_ids))
        self.assertSequenceEqual(
            matching_event_ids,
            extract_event_ids(parsed_result))
        self.assertEqual(parsed_result['count'], len(matching_event_ids))

    def test_GET_query_doesnt_list_devices(self):
        nodes = [
            factory.make_Node(agent_name=factory.make_name('agent-name'))
            for _ in range(3)]
        [factory.make_Event(node=node) for node in nodes]

        # Create devices.
        device_nodes = [
            factory.make_Node(installable=False)
            for _ in range(3)]
        [factory.make_Event(node=node) for node in device_nodes]

        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'level': 'DEBUG',
        }
        )
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        system_ids = extract_event_ids(parsed_result)
        self.assertEqual(
            [],
            [node.system_id for node in
             device_nodes if node.system_id in system_ids],
            "Node listing contains devices.")
        self.assertEqual(parsed_result['count'], len(nodes))

    def test_GET_query_with_zone_filters_by_zone(self):
        non_listed_node = factory.make_Node(
            zone=factory.make_Zone(name='twilight'))
        [factory.make_Event(node=non_listed_node) for _ in range(3)]
        zone = factory.make_Zone()
        node = factory.make_Node(zone=zone)
        matching_event_ids = [
            factory.make_Event(
                node=node).id for _ in range(3)]
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'zone': zone.name,
            'level': 'DEBUG'
        })
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        matching_event_ids = list(reversed(matching_event_ids))
        self.assertSequenceEqual(
            matching_event_ids, extract_event_ids(parsed_result))
        self.assertEqual(parsed_result['count'], len(matching_event_ids))

    def test_GET_query_with_limit_limits_with_most_recent_events(self):
        test_limit = 5
        # Events are returned in id order.
        event_ids = [factory.make_Event().id for _
                     in range(test_limit + 1)]
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'limit': unicode(test_limit),
            'level': 'DEBUG'
        })

        parsed_result = json.loads(response.content)

        self.assertSequenceEqual(
            list(reversed(event_ids))[:test_limit],
            extract_event_ids(parsed_result))
        self.assertEqual(parsed_result['count'], test_limit)

    def test_GET_query_with_limit_over_hard_limit_raises_error_with_msg(self):
        artificial_limit = 5
        test_limit = artificial_limit + 1
        self.patch(events_module, 'MAX_EVENT_LOG_COUNT', artificial_limit)

        [factory.make_Event().id for _ in range(test_limit)]
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'limit': unicode(test_limit),
        })

        expected_msg = ("Requested number of events %d is greater than"
                        " limit: %d" % (test_limit,
                                        events_module.MAX_EVENT_LOG_COUNT))

        observed = response.status_code, response.content
        expected = (
            Equals(httplib.BAD_REQUEST),
            Contains(expected_msg),
        )
        self.assertThat(observed, MatchesListwise(expected))

    def test_GET_query_with_without_limit_limits_to_default_newest(self):
        artificial_limit = 5
        test_limit = artificial_limit + 1
        self.patch(
            events_module,
            'DEFAULT_EVENT_LOG_LIMIT',
            artificial_limit)

        # Nodes are returned in id order.
        event_ids = [factory.make_Event().id for _ in range(test_limit)]
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'level': 'DEBUG'
        })

        parsed_result = json.loads(response.content)

        self.assertSequenceEqual(
            list(reversed(event_ids))[:artificial_limit],
            extract_event_ids(parsed_result))
        self.assertEqual(parsed_result['count'], artificial_limit)

    def test_GET_query_with_start_event_id_with_limit(self):
        test_limit = 5
        (_, _, test_event_3, test_event_4,
         test_event_5) = (factory.make_Event(), factory.make_Event(),
                          factory.make_Event(), factory.make_Event(),
                          factory.make_Event())
        ignore_unused(_)

        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'after': unicode(test_event_3.id),
            'limit': unicode(test_limit),
            'level': 'DEBUG'
        })
        parsed_result = json.loads(response.content)
        expected_result = list(
            [test_event_5.id, test_event_4.id, test_event_3.id])
        observed_result = extract_event_ids(parsed_result)

        self.assertSequenceEqual(
            expected_result, observed_result)
        self.assertEqual(parsed_result['count'], len(expected_result))

    def test_GET_query_with_start_event_id_without_limit(self):
        (_, _, test_event_3, test_event_4,
         test_event_5) = (factory.make_Event(), factory.make_Event(),
                          factory.make_Event(), factory.make_Event(),
                          factory.make_Event())
        ignore_unused(_)

        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'after': unicode(test_event_3.id),
            'level': 'DEBUG'
        })
        parsed_result = json.loads(response.content)
        expected_result = list(
            [test_event_5.id, test_event_4.id, test_event_3.id])
        observed_result = extract_event_ids(parsed_result)

        self.assertSequenceEqual(
            expected_result, observed_result)
        self.assertEqual(parsed_result['count'], len(expected_result))

    def test_GET_query_with_invalid_log_level_raises_error_with_msg(self):
        [factory.make_Event().id for _ in range(3)]
        invalid_level = factory.make_name('invalid_log_level')
        response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'level': invalid_level,
        })

        expected_msg = ("Unknown log level: %s" % invalid_level)

        observed = response.status_code, response.content
        expected = (
            Equals(httplib.BAD_REQUEST),
            Contains(expected_msg),
        )
        self.assertThat(observed, MatchesListwise(expected))

    def test_GET_query_with_log_level_returns_that_level_and_greater(self):
        events_per_level = 2
        event_ids = make_events_with_log_levels(
            self.log_levels,
            events_per_level)

        for idx, level in enumerate(self.log_levels):
            response = self.client.get(reverse('events_handler'), {
                'op': 'query',
                'level': level[0],
            })

            parsed_result = json.loads(response.content)

            expected_result = list(
                reversed(event_ids[:(idx + 1) * events_per_level]))
            observed_result = extract_event_ids(parsed_result)

            self.assertSequenceEqual(
                expected_result, observed_result)
            self.assertEqual(parsed_result['count'], len(expected_result))

    def test_GET_query_with_default_log_level_is_info(self):
        make_events_with_log_levels(self.log_levels)

        info_response = self.client.get(reverse('events_handler'), {
            'op': 'query',
            'level': 'INFO',
        })

        default_response = self.client.get(reverse('events_handler'), {
            'op': 'query',
        })

        expected_result = json.loads(info_response.content)
        observed_result = json.loads(default_response.content)
        expected_result_ids = extract_event_ids(expected_result)

        self.assertSequenceEqual(
            expected_result['events'], observed_result['events'])
        self.assertEqual(observed_result['count'],
                         len(expected_result_ids))
        # Don't compare the URIs. They will be different.

    def test_GET_query_prev_next_uris_preserves_query_params(self):
        test_events = 6
        test_params = list(events_module.EventsHandler.all_params)
        if 'op' in test_params:
            test_params.remove('op')
        expected_uri_path = reverse('events_handler')

        # Try all cardinalities of combinations of query parameters
        for r in range(len(test_params) + 1):
            for params in combinations(test_params, r):
                # Generate test values for all params
                test_values = \
                    {'after': unicode(randint(1, test_events)),
                     'agent_name': factory.make_string(),
                     'id': factory.make_string(),
                     'level': random.choice(LOGGING_LEVELS.values()),
                     'limit': unicode(randint(1, test_events)),
                     'mac_address':
                     unicode(factory.make_MACAddress_with_Node()),
                     'zone': factory.make_string()}

                # Build a query dictionary for the given combination of params
                expected_params = {}
                for param_name in params:
                    expected_params[param_name] = test_values[param_name]

                # Ensure that op is always included
                expected_params['op'] = 'query'

                response = self.client.get(
                    reverse('events_handler'), expected_params)

                self.assertEqual(httplib.OK, response.status_code)

                # Parse the returned JSON and check URI path
                parsed_result = json.loads(response.content)

                next_uri = urlparse(parsed_result['next_uri'])
                prev_uri = urlparse(parsed_result['prev_uri'])

                self.assertEqual(
                    (expected_uri_path, '', '', '', ''),
                    (next_uri.path,
                     next_uri.scheme,
                     next_uri.netloc,
                     next_uri.params,
                     next_uri.fragment))

                self.assertEqual(
                    (expected_uri_path, '', '', '', ''),
                    (prev_uri.path,
                     prev_uri.scheme,
                     prev_uri.netloc,
                     prev_uri.params,
                     prev_uri.fragment))
                self.assertEqual(expected_uri_path, prev_uri.path)

                # Parse URI query strings
                next_uri_params = dict(parse_qsl(
                    next_uri.query,
                    keep_blank_values=True))

                prev_uri_params = dict(parse_qsl(
                    prev_uri.query,
                    keep_blank_values=True))

                # Calculate the expected values for limit
                # and start event id
                limit = events_module.DEFAULT_EVENT_LOG_LIMIT \
                    if 'limit' not in expected_params \
                    else int(expected_params['limit'])

                start_id = 0 if 'after' not in expected_params \
                    else int(expected_params['after'])

                expected_params['after'] = unicode(start_id + limit)
                self.assertDictEqual(expected_params, next_uri_params)

                expected_params['after'] = \
                    unicode(max(start_id - limit, 0))
                self.assertDictEqual(expected_params, prev_uri_params)

    def test_query_num_queries_is_independent_of_num_nodes_and_events(self):
        # 1 query for select event +
        # 1 query to prefetch eventtype +
        # 1 query to prefetch node details
        expected_queries = 3
        events_per_node = 5
        num_nodes_per_group = 5
        events_per_group = num_nodes_per_group * events_per_node

        nodegroup_1 = factory.make_NodeGroup()
        nodegroup_2 = factory.make_NodeGroup()

        self.create_nodes_in_group_with_events(
            nodegroup_1, num_nodes_per_group, events_per_node)

        handler = events_module.EventsHandler()

        query_1_count, query_1_result = count_queries(
            handler.query, RequestFixture(
                {
                    'op': 'query',
                    'level': 'DEBUG',
                }, ['op', 'level']
            ))

        self.create_nodes_in_group_with_events(
            nodegroup_2, num_nodes_per_group, events_per_node)

        query_2_count, query_2_result = count_queries(
            handler.query, RequestFixture(
                {
                    'op': 'query',
                    'level': 'DEBUG',
                }, ['op', 'level']
            ))

        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing an event listing.
        # If this happens, consider your prefetching and adjust accordingly.
        self.assertEquals(events_per_group, int(query_1_result['count']))
        self.assertEquals(
            expected_queries, query_1_count,
            "Number of queries has changed; make sure this is expected.")

        self.assertEquals(events_per_group * 2, int(query_2_result['count']))
        self.assertEquals(
            expected_queries, query_2_count,
            "Number of queries is not independent to the number of nodes.")
