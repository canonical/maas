# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver.stats."""


import base64
import json

from django.db import transaction
import requests as requests_module
from twisted.application.internet import TimerService
from twisted.internet.defer import fail

from maasserver import stats
from maasserver.enum import IPADDRESS_TYPE, IPRANGE_TYPE, NODE_STATUS
from maasserver.models import Config, Fabric, Space, Subnet, VLAN
from maasserver.stats import (
    get_kvm_pods_stats,
    get_maas_stats,
    get_machine_stats,
    get_machines_by_architecture,
    get_request_params,
    make_maas_user_agent_request,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting.matchers import MockCalledOnce, MockNotCalled
from maastesting.testcase import MAASTestCase
from maastesting.twisted import extract_result
from provisioningserver.utils.twisted import asynchronous


class TestMAASStats(MAASServerTestCase):
    def make_pod(self, cpu=0, mem=0, cpu_over_commit=1, mem_over_commit=1):
        # Make one pod
        zone = factory.make_Zone()
        pool = factory.make_ResourcePool()
        ip = factory.make_ipv4_address()
        power_parameters = {
            "power_address": "qemu+ssh://%s/system" % ip,
            "power_pass": "pass",
        }
        return factory.make_Pod(
            pod_type="virsh",
            zone=zone,
            pool=pool,
            cores=cpu,
            memory=mem,
            cpu_over_commit_ratio=cpu_over_commit,
            memory_over_commit_ratio=mem_over_commit,
            parameters=power_parameters,
        )

    def test_get_machines_by_architecture(self):
        arches = [
            "amd64/generic",
            "s390x/generic",
            "ppc64el/generic",
            "arm64/generic",
            "i386/generic",
        ]
        for arch in arches:
            factory.make_Machine(architecture=arch)
        stats = get_machines_by_architecture()
        compare = {"amd64": 1, "i386": 1, "arm64": 1, "ppc64el": 1, "s390x": 1}
        self.assertEqual(stats, compare)

    def test_get_kvm_pods_stats(self):
        pod1 = self.make_pod(
            cpu=10, mem=100, cpu_over_commit=2, mem_over_commit=3
        )
        pod2 = self.make_pod(
            cpu=20, mem=200, cpu_over_commit=3, mem_over_commit=2
        )

        total_cores = pod1.cores + pod2.cores
        total_memory = pod1.memory + pod2.memory
        over_cores = (
            pod1.cores * pod1.cpu_over_commit_ratio
            + pod2.cores * pod2.cpu_over_commit_ratio
        )
        over_memory = (
            pod1.memory * pod1.memory_over_commit_ratio
            + pod2.memory * pod2.memory_over_commit_ratio
        )

        stats = get_kvm_pods_stats()
        compare = {
            "kvm_pods": 2,
            "kvm_machines": 0,
            "kvm_available_resources": {
                "cores": total_cores,
                "memory": total_memory,
                "over_cores": over_cores,
                "over_memory": over_memory,
                "storage": 0,
            },
            "kvm_utilized_resources": {"cores": 0, "memory": 0, "storage": 0},
        }
        self.assertEqual(compare, stats)

    def test_get_kvm_pods_stats_no_pod(self):
        self.assertEqual(
            get_kvm_pods_stats(),
            {
                "kvm_pods": 0,
                "kvm_machines": 0,
                "kvm_available_resources": {
                    "cores": 0,
                    "memory": 0,
                    "storage": 0,
                    "over_cores": 0,
                    "over_memory": 0,
                },
                "kvm_utilized_resources": {
                    "cores": 0,
                    "memory": 0,
                    "storage": 0,
                },
            },
        )

    def test_get_maas_stats(self):
        # Make one component of everything
        factory.make_RegionRackController()
        factory.make_RegionController()
        factory.make_RackController()
        factory.make_Machine(cpu_count=2, memory=200, status=NODE_STATUS.READY)
        factory.make_Machine(status=NODE_STATUS.READY)
        factory.make_Machine(status=NODE_STATUS.NEW)
        for _ in range(4):
            factory.make_Machine(status=NODE_STATUS.ALLOCATED)
        factory.make_Machine(
            cpu_count=3, memory=100, status=NODE_STATUS.FAILED_DEPLOYMENT
        )
        for _ in range(2):
            factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        factory.make_Device()
        factory.make_Device()

        subnets = Subnet.objects.all()
        v4 = [net for net in subnets if net.get_ip_version() == 4]
        v6 = [net for net in subnets if net.get_ip_version() == 6]

        stats = get_maas_stats()
        machine_stats = get_machine_stats()

        # Due to floating point calculation subtleties, sometimes the value the
        # database returns is off by one compared to the value Python
        # calculates, so just get it directly from the database for the test.
        total_storage = machine_stats["total_storage"]

        expected = {
            "controllers": {"regionracks": 1, "regions": 1, "racks": 1},
            "nodes": {"machines": 10, "devices": 2},
            "machine_stats": {
                "total_cpu": 5,
                "total_mem": 300,
                "total_storage": total_storage,
            },
            "machine_status": {
                "new": 1,
                "ready": 2,
                "allocated": 4,
                "deployed": 2,
                "commissioning": 0,
                "testing": 0,
                "deploying": 0,
                "failed_deployment": 1,
                "failed_commissioning": 0,
                "failed_testing": 0,
                "broken": 0,
            },
            "network_stats": {
                "spaces": Space.objects.count(),
                "fabrics": Fabric.objects.count(),
                "vlans": VLAN.objects.count(),
                "subnets_v4": len(v4),
                "subnets_v6": len(v6),
            },
        }
        self.assertEqual(json.loads(stats), expected)

    def test_get_maas_stats_no_machines(self):
        expected = {
            "controllers": {"regionracks": 0, "regions": 0, "racks": 0},
            "nodes": {"machines": 0, "devices": 0},
            "machine_stats": {
                "total_cpu": 0,
                "total_mem": 0,
                "total_storage": 0,
            },
            "machine_status": {
                "new": 0,
                "ready": 0,
                "allocated": 0,
                "deployed": 0,
                "commissioning": 0,
                "testing": 0,
                "deploying": 0,
                "failed_deployment": 0,
                "failed_commissioning": 0,
                "failed_testing": 0,
                "broken": 0,
            },
            "network_stats": {
                "spaces": 0,
                "fabrics": 0,
                "vlans": 0,
                "subnets_v4": 0,
                "subnets_v6": 0,
            },
        }
        self.assertEqual(json.loads(get_maas_stats()), expected)

    def test_get_request_params_returns_params(self):
        factory.make_RegionRackController()
        params = {
            "data": base64.b64encode(
                json.dumps(get_maas_stats()).encode()
            ).decode()
        }
        self.assertEqual(params, get_request_params())

    def test_make_user_agent_request(self):
        factory.make_RegionRackController()
        mock = self.patch(requests_module, "get")
        make_maas_user_agent_request()
        self.assertThat(mock, MockCalledOnce())


class TestGetSubnetsUtilisationStats(MAASServerTestCase):
    def test_stats_totals(self):
        factory.make_Subnet(cidr="1.2.0.0/16", gateway_ip="1.2.0.254")
        factory.make_Subnet(cidr="::1/128", gateway_ip="")
        self.assertEqual(
            stats.get_subnets_utilisation_stats(),
            {
                "1.2.0.0/16": {
                    "available": 2 ** 16 - 3,
                    "dynamic_available": 0,
                    "dynamic_used": 0,
                    "reserved_available": 0,
                    "reserved_used": 0,
                    "static": 0,
                    "unavailable": 1,
                },
                "::1/128": {
                    "available": 1,
                    "dynamic_available": 0,
                    "dynamic_used": 0,
                    "reserved_available": 0,
                    "reserved_used": 0,
                    "static": 0,
                    "unavailable": 0,
                },
            },
        )

    def test_stats_dynamic(self):
        subnet = factory.make_Subnet(cidr="1.2.0.0/16", gateway_ip="1.2.0.254")
        factory.make_IPRange(
            subnet=subnet,
            start_ip="1.2.0.11",
            end_ip="1.2.0.20",
            alloc_type=IPRANGE_TYPE.DYNAMIC,
        )
        factory.make_IPRange(
            subnet=subnet,
            start_ip="1.2.0.51",
            end_ip="1.2.0.60",
            alloc_type=IPRANGE_TYPE.DYNAMIC,
        )
        factory.make_StaticIPAddress(
            ip="1.2.0.15", alloc_type=IPADDRESS_TYPE.DHCP, subnet=subnet
        )
        factory.make_StaticIPAddress(
            ip="1.2.0.52", alloc_type=IPADDRESS_TYPE.DHCP, subnet=subnet
        )
        self.assertEqual(
            stats.get_subnets_utilisation_stats(),
            {
                "1.2.0.0/16": {
                    "available": 2 ** 16 - 23,
                    "dynamic_available": 18,
                    "dynamic_used": 2,
                    "reserved_available": 0,
                    "reserved_used": 0,
                    "static": 0,
                    "unavailable": 21,
                }
            },
        )

    def test_stats_reserved(self):
        subnet = factory.make_Subnet(cidr="1.2.0.0/16", gateway_ip="1.2.0.254")
        factory.make_IPRange(
            subnet=subnet,
            start_ip="1.2.0.11",
            end_ip="1.2.0.20",
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        factory.make_IPRange(
            subnet=subnet,
            start_ip="1.2.0.51",
            end_ip="1.2.0.60",
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        factory.make_StaticIPAddress(
            ip="1.2.0.15",
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            subnet=subnet,
        )
        self.assertEqual(
            stats.get_subnets_utilisation_stats(),
            {
                "1.2.0.0/16": {
                    "available": 2 ** 16 - 23,
                    "dynamic_available": 0,
                    "dynamic_used": 0,
                    "reserved_available": 19,
                    "reserved_used": 1,
                    "static": 0,
                    "unavailable": 21,
                }
            },
        )

    def test_stats_static(self):
        subnet = factory.make_Subnet(cidr="1.2.0.0/16", gateway_ip="1.2.0.254")
        for n in (10, 20, 30):
            factory.make_StaticIPAddress(
                ip="1.2.0.{}".format(n),
                alloc_type=IPADDRESS_TYPE.STICKY,
                subnet=subnet,
            )
        self.assertEqual(
            stats.get_subnets_utilisation_stats(),
            {
                "1.2.0.0/16": {
                    "available": 2 ** 16 - 6,
                    "dynamic_available": 0,
                    "dynamic_used": 0,
                    "reserved_available": 0,
                    "reserved_used": 0,
                    "static": 3,
                    "unavailable": 4,
                }
            },
        )

    def test_stats_all(self):
        subnet = factory.make_Subnet(cidr="1.2.0.0/16", gateway_ip="1.2.0.254")
        factory.make_IPRange(
            subnet=subnet,
            start_ip="1.2.0.11",
            end_ip="1.2.0.20",
            alloc_type=IPRANGE_TYPE.DYNAMIC,
        )
        factory.make_IPRange(
            subnet=subnet,
            start_ip="1.2.0.51",
            end_ip="1.2.0.70",
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        factory.make_StaticIPAddress(
            ip="1.2.0.12", alloc_type=IPADDRESS_TYPE.DHCP, subnet=subnet
        )
        for n in (60, 61):
            factory.make_StaticIPAddress(
                ip="1.2.0.{}".format(n),
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
                subnet=subnet,
            )
        for n in (80, 90, 100):
            factory.make_StaticIPAddress(
                ip="1.2.0.{}".format(n),
                alloc_type=IPADDRESS_TYPE.STICKY,
                subnet=subnet,
            )
        self.assertEqual(
            stats.get_subnets_utilisation_stats(),
            {
                "1.2.0.0/16": {
                    "available": 2 ** 16 - 36,
                    "dynamic_available": 9,
                    "dynamic_used": 1,
                    "reserved_available": 18,
                    "reserved_used": 2,
                    "static": 3,
                    "unavailable": 34,
                }
            },
        )


class TestStatsService(MAASTestCase):
    """Tests for `ImportStatsService`."""

    def test_is_a_TimerService(self):
        service = stats.StatsService()
        self.assertIsInstance(service, TimerService)

    def test_runs_once_a_day(self):
        service = stats.StatsService()
        self.assertEqual(86400, service.step)

    def test_calls__maybe_make_stats_request(self):
        service = stats.StatsService()
        self.assertEqual(
            (service.maybe_make_stats_request, (), {}), service.call
        )

    def test_maybe_make_stats_request_does_not_error(self):
        service = stats.StatsService()
        deferToDatabase = self.patch(stats, "deferToDatabase")
        exception_type = factory.make_exception_type()
        deferToDatabase.return_value = fail(exception_type())
        d = service.maybe_make_stats_request()
        self.assertIsNone(extract_result(d))


class TestStatsServiceAsync(MAASTransactionServerTestCase):
    """Tests for the async parts of `StatsService`."""

    def test_maybe_make_stats_request_makes_request(self):
        mock_call = self.patch(stats, "make_maas_user_agent_request")

        with transaction.atomic():
            Config.objects.set_config("enable_analytics", True)

        service = stats.StatsService()
        maybe_make_stats_request = asynchronous(
            service.maybe_make_stats_request
        )
        maybe_make_stats_request().wait(5)

        self.assertThat(mock_call, MockCalledOnce())

    def test_maybe_make_stats_request_doesnt_make_request(self):
        mock_call = self.patch(stats, "make_maas_user_agent_request")

        with transaction.atomic():
            Config.objects.set_config("enable_analytics", False)

        service = stats.StatsService()
        maybe_make_stats_request = asynchronous(
            service.maybe_make_stats_request
        )
        maybe_make_stats_request().wait(5)

        self.assertThat(mock_call, MockNotCalled())
