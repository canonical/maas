# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Discoveries API."""

__all__ = []

from datetime import datetime
import http.client
import json
import random

from django.conf import settings
from django.core.urlresolvers import reverse
from maasserver.api import discoveries as discoveries_module
from maasserver.api.discoveries import (
    get_controller_summary,
    get_failure_summary,
    interpret_scan_all_rack_networks_rpc_results,
    scan_all_rack_networks,
)
from maasserver.clusterrpc.utils import RPCResults
from maasserver.dbviews import register_view
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.matchers import HasStatusCode
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import (
    DocTestMatches,
    MockCalledOnceWith,
)
from maastesting.testcase import MAASTestCase
from netaddr import IPNetwork
from provisioningserver.rpc import cluster
from testtools.matchers import (
    Equals,
    HasLength,
)
from twisted.python.failure import Failure


def timestamp_format(time):
    """Convert the specified `time` to the string we expect Pison to output."""
    if time.microsecond == 0:
        return time.strftime("%Y-%m-%dT%H:%M:%S")
    else:
        return time.strftime(
            "%%Y-%%m-%%dT%%H:%%M:%%S.%03d" % int(time.microsecond / 1000))


def get_discoveries_uri():
    """Return a Discovery's URI on the API."""
    return reverse('discoveries_handler', args=[])


def get_discovery_uri(discovery):
    """Return a Discovery URI on the API."""
    return reverse(
        'discovery_handler', args=[discovery.discovery_id])


def get_discovery_uri_by_specifiers(specifiers):
    """Return a Discovery URI on the API."""
    return reverse(
        'discovery_handler', args=[specifiers])


def make_discoveries(count=3, interface=None):
    return [
        factory.make_Discovery(
            interface=interface, time=time,
            updated=datetime.fromtimestamp(time))
        for time in range(count)
        ]


class TestDiscoveriesAPI(APITestCase.ForUser):

    def setUp(self):
        super().setUp()
        register_view("maasserver_discovery")

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/discovery/', get_discoveries_uri())

    def get_api_results(self, *args, **kwargs):
        uri = get_discoveries_uri()
        response = self.client.get(uri, *args, **kwargs)
        self.assertThat(response, HasStatusCode(http.client.OK))
        results = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        return results

    def post_api_response(self, *args, **kwargs):
        uri = get_discoveries_uri()
        return self.client.post(uri, *args, **kwargs)

    def post_api_results(self, *args, **kwargs):
        uri = get_discoveries_uri()
        response = self.client.post(uri, *args, **kwargs)
        self.assertThat(response, HasStatusCode(http.client.OK))
        results = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        return results

    def test_read(self):
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        discoveries = make_discoveries(interface=iface)
        results = self.get_api_results()
        self.assertThat(results, HasLength(3))
        expected_ids = [discovery.discovery_id for discovery in discoveries]
        result_ids = [discovery["discovery_id"] for discovery in results]
        self.assertItemsEqual(expected_ids, result_ids)

    def test_read_sorts_by_last_seen(self):
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        make_discoveries(interface=iface)
        results = self.get_api_results()
        self.assertTrue(results[0]['last_seen'] >= results[2]['last_seen'])
        self.assertTrue(results[0]['last_seen'] >= results[1]['last_seen'])
        self.assertTrue(results[1]['last_seen'] >= results[2]['last_seen'])

    def test__by_unknown_mac(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        discovery = factory.make_Discovery(interface=iface)
        results = self.get_api_results({'op': 'by_unknown_mac'})
        self.assertThat(len(results), Equals(1))
        factory.make_Interface(mac_address=discovery.mac_address)
        # Now that we have a known interface with the same MAC, the discovery
        # should disappear from this query.
        results = self.get_api_results({'op': 'by_unknown_mac'})
        self.assertThat(len(results), Equals(0))

    def test__by_unknown_ip(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        discovery = factory.make_Discovery(interface=iface, ip="10.0.0.1")
        results = self.get_api_results({'op': 'by_unknown_ip'})
        self.assertThat(len(results), Equals(1))
        factory.make_StaticIPAddress(ip=discovery.ip, cidr="10.0.0.0/8")
        # Now that we have a known IP address that matches, the discovery
        # should disappear from this query.
        results = self.get_api_results({'op': 'by_unknown_ip'})
        self.assertThat(len(results), Equals(0))

    def test__by_unknown_ip_and_mac__known_ip(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        discovery = factory.make_Discovery(interface=iface, ip="10.0.0.1")
        results = self.get_api_results({'op': 'by_unknown_ip_and_mac'})
        self.assertThat(len(results), Equals(1))
        factory.make_StaticIPAddress(ip=discovery.ip, cidr="10.0.0.0/8")
        # Known IP address, unexpected MAC.
        results = self.get_api_results({'op': 'by_unknown_ip_and_mac'})
        self.assertThat(len(results), Equals(0))

    def test__by_unknown_ip_and_mac__known_mac(self):
        rack = factory.make_RackController()
        iface = factory.make_Interface(node=rack)
        discovery = factory.make_Discovery(interface=iface)
        results = self.get_api_results({'op': 'by_unknown_ip_and_mac'})
        self.assertThat(len(results), Equals(1))
        # Known MAC, unknown IP.
        factory.make_Interface(mac_address=discovery.mac_address)
        results = self.get_api_results({'op': 'by_unknown_ip_and_mac'})
        self.assertThat(len(results), Equals(0))

    def test__scan__fails_scan_all_if_not_forced(self):
        scan_all_rack_networks_mock = self.patch(
            discoveries_module.scan_all_rack_networks)
        result = {"result": factory.make_name()}
        scan_all_rack_networks_mock.return_value = result
        response = self.post_api_response({'op': 'scan'})
        self.assertThat(
            response, HasStatusCode(http.client.BAD_REQUEST))

    def test__scan__threads_must_be_number(self):
        scan_all_rack_networks_mock = self.patch(
            discoveries_module.scan_all_rack_networks)
        result = {"result": factory.make_name()}
        scan_all_rack_networks_mock.return_value = result
        response = self.post_api_response({'op': 'scan', 'threads': 'x'})
        self.assertThat(
            response, HasStatusCode(http.client.BAD_REQUEST))

    def test__scan__calls_scan_all_networks_with_scan_all_if_forced(self):
        scan_all_rack_networks_mock = self.patch(
            discoveries_module.scan_all_rack_networks)
        result = {"result": factory.make_name()}
        scan_all_rack_networks_mock.return_value = result
        result = self.post_api_results({'op': 'scan', 'force': 'true'})
        self.assertThat(result, Equals(result))
        self.assertThat(scan_all_rack_networks_mock, MockCalledOnceWith(
            scan_all=True, ping=False, slow=False, threads=None))

    def test__scan__passes_ping(self):
        scan_all_rack_networks_mock = self.patch(
            discoveries_module.scan_all_rack_networks)
        result = {"result": factory.make_name()}
        scan_all_rack_networks_mock.return_value = result
        result = self.post_api_results({
            'op': 'scan',
            'force': 'true',
            'always_use_ping': 'true'
        })
        self.assertThat(result, Equals(result))
        self.assertThat(scan_all_rack_networks_mock, MockCalledOnceWith(
            scan_all=True, ping=True, slow=False, threads=None))

    def test__scan__passes_slow(self):
        scan_all_rack_networks_mock = self.patch(
            discoveries_module.scan_all_rack_networks)
        result = {"result": factory.make_name()}
        scan_all_rack_networks_mock.return_value = result
        result = self.post_api_results({
            'op': 'scan',
            'force': 'true',
            'slow': 'true'
        })
        self.assertThat(result, Equals(result))
        self.assertThat(scan_all_rack_networks_mock, MockCalledOnceWith(
            scan_all=True, ping=False, slow=True, threads=None))

    def test__scan__passes_threads(self):
        scan_all_rack_networks_mock = self.patch(
            discoveries_module.scan_all_rack_networks)
        result = {"result": factory.make_name()}
        scan_all_rack_networks_mock.return_value = result
        result = self.post_api_results({
            'op': 'scan',
            'force': 'true',
            'threads': '3.14'
        })
        self.assertThat(result, Equals(result))
        self.assertThat(scan_all_rack_networks_mock, MockCalledOnceWith(
            scan_all=True, ping=False, slow=False, threads=3))

    def test__scan__calls_scan_all_networks_with_specified_cidrs(self):
        scan_all_rack_networks_mock = self.patch(
            discoveries_module.scan_all_rack_networks)
        result = {"result": factory.make_name()}
        scan_all_rack_networks_mock.return_value = result
        result = self.post_api_results({
            'op': 'scan',
            'force': 'true',
            'cidr': ['192.168.0.0/24', '192.168.1.0/24']
        })
        self.assertThat(result, Equals(result))
        self.assertThat(
            scan_all_rack_networks_mock, MockCalledOnceWith(cidrs=[
                IPNetwork('192.168.0.0/24'),
                IPNetwork('192.168.1.0/24')],
                ping=False, slow=False, threads=None
            ))

    def test__scan__with_invalid_cidrs_fails(self):
        scan_all_rack_networks_mock = self.patch(
            discoveries_module.scan_all_rack_networks)
        result = {"result": factory.make_name()}
        scan_all_rack_networks_mock.return_value = result
        response = self.post_api_response({
            'op': 'scan',
            'cidr': ['x.x.x.x/y']
        })
        self.assertThat(
            response, HasStatusCode(http.client.BAD_REQUEST))

    def test__scan__with_no_cidrs_does_not_call_scan_all_networks(self):
        scan_all_rack_networks_mock = self.patch(
            discoveries_module.scan_all_rack_networks)
        result = {"result": factory.make_name()}
        scan_all_rack_networks_mock.return_value = result
        response = self.post_api_response({'op': 'scan'})
        self.assertThat(
            response, HasStatusCode(http.client.BAD_REQUEST))

    def test__clear_not_allowed_for_non_admin(self):
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        make_discoveries(interface=iface, count=3)
        uri = get_discoveries_uri()
        response = self.client.post(uri, {'op': 'clear'})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code,
            response.content)

    def test__clear_requires_parameters(self):
        self.become_admin()
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        make_discoveries(interface=iface, count=3)
        uri = get_discoveries_uri()
        response = self.client.post(uri, {'op': 'clear'})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code,
            response.content)

    def test__clear_all_allowed_for_admin(self):
        self.become_admin()
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        make_discoveries(interface=iface, count=3)
        uri = get_discoveries_uri()
        response = self.client.post(uri, {'op': 'clear', 'all': 'true'})
        self.assertEqual(204, response.status_code, response.content)

    def test__clear_mdns_allowed_for_admin(self):
        self.become_admin()
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        make_discoveries(interface=iface, count=3)
        uri = get_discoveries_uri()
        response = self.client.post(uri, {'op': 'clear', 'mdns': 'true'})
        self.assertEqual(204, response.status_code, response.content)

    def test__clear_neighbours_allowed_for_admin(self):
        self.become_admin()
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        make_discoveries(interface=iface, count=3)
        uri = get_discoveries_uri()
        response = self.client.post(uri, {'op': 'clear', 'neighbours': 'true'})
        self.assertEqual(204, response.status_code, response.content)


class TestDiscoveryAPI(APITestCase.ForUser):

    def setUp(self):
        super().setUp()
        register_view("maasserver_discovery")

    def test_handler_path(self):
        discovery = factory.make_Discovery()
        self.assertEqual(
            '/api/2.0/discovery/%s/' % discovery.discovery_id,
            get_discovery_uri(discovery))

    def test_read(self):
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        discoveries = make_discoveries(interface=iface)
        discovery = discoveries[1]
        uri = get_discovery_uri(discovery)
        response = self.client.get(uri)
        self.assertThat(response, HasStatusCode(http.client.OK))
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        # Spot check expected values in the results
        self.assertThat(
            result["resource_uri"],
            Equals(get_discovery_uri(discovery)))
        self.assertThat(
            result["observer"]["system_id"],
            Equals(rack.system_id))
        self.assertThat(
            result["observer"]["hostname"],
            Equals(rack.hostname))
        self.assertThat(
            result["observer"]["interface_name"],
            Equals(iface.name))
        self.assertThat(
            result["observer"]["interface_id"],
            Equals(iface.id))
        self.assertThat(
            result["ip"],
            Equals(discovery.ip))
        self.assertThat(
            result["mac_address"],
            Equals(discovery.mac_address))
        self.assertThat(
            result["hostname"],
            Equals(discovery.hostname))
        self.assertThat(
            result["last_seen"],
            Equals(timestamp_format(discovery.last_seen)))

    def test_read_by_specifiers(self):
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        [discovery] = make_discoveries(interface=iface, count=1)
        uri = get_discovery_uri_by_specifiers("ip:" + str(discovery.ip))
        response = self.client.get(uri)
        self.assertThat(response, HasStatusCode(http.client.OK))
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertThat(
            result["ip"],
            Equals(discovery.ip))

    def test_read_404_when_bad_id(self):
        uri = reverse(
            'discovery_handler', args=[random.randint(10000, 20000)])
        response = self.client.get(uri)
        self.assertThat(response, HasStatusCode(http.client.NOT_FOUND))

    def test_update_not_allowed(self):
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        discoveries = make_discoveries(interface=iface)
        discovery = discoveries[1]
        uri = get_discovery_uri(discovery)
        response = self.client.put(uri, {
            "ip": factory.make_ip_address(),
        })
        self.assertThat(
            response, HasStatusCode(http.client.METHOD_NOT_ALLOWED))

    def test_delete_not_allowed_even_for_admin(self):
        self.become_admin()
        rack = factory.make_RackController()
        iface = rack.interface_set.first()
        discoveries = make_discoveries(interface=iface, count=3)
        discovery = discoveries[1]
        uri = get_discovery_uri(discovery)
        response = self.client.delete(uri)
        self.assertThat(
            response, HasStatusCode(http.client.METHOD_NOT_ALLOWED))


def make_RPCResults(
        results=None, failures=None, available=None, unavailable=None,
        success=None, failed=None, timeout=None):
    """Creates an `RPCResults` namedtuple without requiring all arguments."""
    return RPCResults(
        results, failures, available, unavailable, success, failed, timeout)


class TestInterpretsScanAllRackNetworksRPCResults(MAASTestCase):

    def test__no_racks_available(self):
        results = make_RPCResults(available=[], failed=[])
        result = interpret_scan_all_rack_networks_rpc_results(results)
        self.assertThat(result, DocTestMatches(
            "Unable to initiate network scanning on any rack controller..."))

    def test__scan_not_started_on_at_least_one_rack(self):
        results = make_RPCResults(
            available=['x'], unavailable=['y', 'z'], failed=[])
        result = interpret_scan_all_rack_networks_rpc_results(results)
        self.assertThat(result, DocTestMatches(
            "Scanning could not be started on 2 rack..."))

    def test__scan_in_progress(self):
        results = make_RPCResults(
            available=['x'], unavailable=[], failed=[])
        result = interpret_scan_all_rack_networks_rpc_results(results)
        self.assertThat(result, DocTestMatches(
            "Scanning is in-progress..."))

    def test__scan_failed_on_at_least_one_rack(self):
        results = make_RPCResults(
            available=['x'], failed=['v', 'w'], unavailable=['y', 'z'])
        result = interpret_scan_all_rack_networks_rpc_results(results)
        self.assertThat(result, DocTestMatches(
            "Scanning could not be started...In addition, a scan was already "
            "in-progress on 2..."))

    def test__failed_rack(self):
        results = make_RPCResults(
            available=['w'], failed=['w'], unavailable=[])
        result = interpret_scan_all_rack_networks_rpc_results(results)
        self.assertThat(result, DocTestMatches(
            "A scan was already in-progress on 1 rack..."))


class TestScanAllRackNetworksInterpretsRPCResults(MAASServerTestCase):

    def setUp(self):
        super().setUp()
        self.result = factory.make_name("result")
        interpret_result_mock = self.patch(
            discoveries_module.interpret_scan_all_rack_networks_rpc_results)
        interpret_result_mock.return_value = self.result
        self.call_racks_sync_mock = self.patch(
            discoveries_module, 'call_racks_synchronously')
        r1 = factory.make_RackController()
        r2 = factory.make_RackController()
        r3 = factory.make_RackController()
        r4 = factory.make_RackController()
        r5 = factory.make_RackController()
        self.available = [r1, r2, r3, r5]
        self.unavailable = [r4]
        self.started = [r1, r2]
        self.failed = [r3]
        self.timed_out = [r5]
        self.failures = [Failure(Exception("foo"))]
        self.call_racks_sync_mock.return_value = make_RPCResults(
            available=self.available, unavailable=self.unavailable,
            success=self.started, failures=self.failures, failed=self.failed,
            timeout=self.timed_out)

    def test__populates_results_correctly(self):
        result = scan_all_rack_networks()
        self.assertThat(result, Equals(
            {
                "result": self.result,
                "scan_started_on":
                    get_controller_summary(self.started),
                "scan_failed_on":
                    get_controller_summary(self.failed),
                "scan_attempted_on":
                    get_controller_summary(self.available),
                "failed_to_connect_to":
                    get_controller_summary(self.unavailable),
                "rpc_call_timed_out_on":
                    get_controller_summary(self.timed_out),
                "failures":
                    get_failure_summary(self.failures),
            }
        ))

    def test__results_can_be_converted_to_json_and_back(self):
        result = scan_all_rack_networks()
        json_result = json.dumps(result)
        self.assertThat(json.loads(json_result), Equals(result))

    def test__calls_racks_synchronously(self):
        scan_all_rack_networks()
        self.assertThat(
            self.call_racks_sync_mock, MockCalledOnceWith(
                cluster.ScanNetworks, kwargs={}))

    def test__calls_racks_synchronously_with_scan_all(self):
        scan_all_rack_networks(scan_all=True)
        self.assertThat(
            self.call_racks_sync_mock, MockCalledOnceWith(
                cluster.ScanNetworks, kwargs={'scan_all': True}))

    def test__calls_racks_synchronously_with_cidrs(self):
        scan_all_rack_networks(cidrs=['a', 'b', 'c'])
        self.assertThat(
            self.call_racks_sync_mock, MockCalledOnceWith(
                cluster.ScanNetworks, kwargs={'cidrs': ['a', 'b', 'c']}))

    def test__calls_racks_synchronously_with_force_ping(self):
        scan_all_rack_networks(ping=True)
        self.assertThat(
            self.call_racks_sync_mock, MockCalledOnceWith(
                cluster.ScanNetworks, kwargs={'force_ping': True}))

    def test__calls_racks_synchronously_with_threads(self):
        threads = random.randint(1, 99)
        scan_all_rack_networks(threads=threads)
        self.assertThat(
            self.call_racks_sync_mock, MockCalledOnceWith(
                cluster.ScanNetworks, kwargs={'threads': threads}))

    def test__calls_racks_synchronously_with_slow(self):
        scan_all_rack_networks(slow=True)
        self.assertThat(
            self.call_racks_sync_mock, MockCalledOnceWith(
                cluster.ScanNetworks, kwargs={'slow': True}))
