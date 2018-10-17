# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver.stats."""

__all__ = []

import base64
from collections import Counter
import json

from django.db import transaction
from maasserver import stats
from maasserver.enum import NODE_STATUS
from maasserver.models import (
    Config,
    Fabric,
    Node,
    Space,
    Subnet,
    VLAN,
)
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
from maastesting.matchers import (
    MockCalledOnce,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from maastesting.twisted import extract_result
from provisioningserver.utils.twisted import asynchronous
import requests as requests_module
from twisted.application.internet import TimerService
from twisted.internet.defer import fail


class TestMAASStats(MAASServerTestCase):

    def make_pod(self, cpu=0, mem=0, cpu_over_commit=1, mem_over_commit=1):
        # Make one pod
        zone = factory.make_Zone()
        pool = factory.make_ResourcePool()
        ip = factory.make_ipv4_address()
        power_parameters = {
            'power_address': 'qemu+ssh://%s/system' % ip,
            'power_pass': 'pass',
        }
        return factory.make_Pod(
            pod_type='virsh', zone=zone, pool=pool,
            cores=cpu, memory=mem,
            cpu_over_commit_ratio=cpu_over_commit,
            memory_over_commit_ratio=mem_over_commit,
            parameters=power_parameters)

    def test_get_machines_by_architecture(self):
        arches = [
            'amd64/generic', 's390x/generic', 'ppc64el/generic',
            'arm64/generic', 'i386/generic']
        for arch in arches:
            factory.make_Machine(architecture=arch)
        stats = get_machines_by_architecture()
        compare = {
            "amd64": 1,
            "i386": 1,
            "arm64": 1,
            "ppc64el": 1,
            "s390x": 1,
        }
        self.assertEquals(stats, compare)

    def test_get_kvm_pods_stats(self):
        pod1 = self.make_pod(
            cpu=10, mem=100, cpu_over_commit=2, mem_over_commit=3)
        pod2 = self.make_pod(
            cpu=20, mem=200, cpu_over_commit=3, mem_over_commit=2)

        total_cores = pod1.cores + pod2.cores
        total_memory = pod1.memory + pod2.memory
        over_cores = (
            pod1.cores * pod1.cpu_over_commit_ratio +
            pod2.cores * pod2.cpu_over_commit_ratio)
        over_memory = (
            pod1.memory * pod1.memory_over_commit_ratio +
            pod2.memory * pod2.memory_over_commit_ratio)

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
            "kvm_utilized_resources": {
                'cores': 0,
                'memory': 0,
                'storage': 0
            },
        }
        self.assertEquals(compare, stats)

    def test_get_maas_stats(self):
        # Make one component of everything
        factory.make_RegionRackController()
        factory.make_RegionController()
        factory.make_RackController()
        factory.make_Machine(cpu_count=2, memory=200, status=4)
        factory.make_Machine(cpu_count=3, memory=100, status=11)
        factory.make_Device()

        subnets = Subnet.objects.all()
        v4 = [net for net in subnets if net.get_ip_version() == 4]
        v6 = [net for net in subnets if net.get_ip_version() == 6]

        stats = get_maas_stats()
        machine_stats = get_machine_stats()

        # Due to floating point calculation subtleties, sometimes the value the
        # database returns is off by one compared to the value Python
        # calculates, so just get it directly from the database for the test.
        total_storage = machine_stats['total_storage']

        node_status = Node.objects.values_list('status', flat=True)
        node_status = Counter(node_status)

        compare = {
            "controllers": {
                "regionracks": 1,
                "regions": 1,
                "racks": 1,
            },
            "nodes": {
                "machines": 2,
                "devices": 1,
            },
            "machine_stats": {
                "total_cpu": 5,
                "total_mem": 300,
                "total_storage": total_storage,
            },
            "machine_status": {
                "new": node_status.get(NODE_STATUS.NEW, 0),
                "ready": node_status.get(NODE_STATUS.READY, 0),
                "allocated": node_status.get(NODE_STATUS.ALLOCATED, 0),
                "deployed": node_status.get(NODE_STATUS.DEPLOYED, 0),
                "commissioning": node_status.get(
                    NODE_STATUS.COMMISSIONING, 0),
                "testing": node_status.get(
                    NODE_STATUS.TESTING, 0),
                "deploying": node_status.get(
                    NODE_STATUS.DEPLOYING, 0),
                "failed_deployment": node_status.get(
                    NODE_STATUS.FAILED_DEPLOYMENT, 0),
                "failed_commissioning": node_status.get(
                    NODE_STATUS.COMMISSIONING, 0),
                "failed_testing": node_status.get(
                    NODE_STATUS.FAILED_TESTING, 0),
                "broken": node_status.get(NODE_STATUS.BROKEN, 0),
            },
            "network_stats": {
                "spaces": Space.objects.count(),
                "fabrics": Fabric.objects.count(),
                "vlans": VLAN.objects.count(),
                "subnets_v4": len(v4),
                "subnets_v6": len(v6),
            },
        }
        self.assertEquals(stats, json.dumps(compare))

    def test_get_request_params_returns_params(self):
        factory.make_RegionRackController()
        params = {
            "data": base64.b64encode(
                json.dumps(get_maas_stats()).encode()).decode()
        }
        self.assertEquals(params, get_request_params())

    def test_make_user_agent_request(self):
        factory.make_RegionRackController()
        mock = self.patch(requests_module, "get")
        make_maas_user_agent_request()
        self.assertThat(mock, MockCalledOnce())


class TestStatsService(MAASTestCase):
    """Tests for `ImportStatsService`."""

    def test__is_a_TimerService(self):
        service = stats.StatsService()
        self.assertIsInstance(service, TimerService)

    def test__runs_once_a_day(self):
        service = stats.StatsService()
        self.assertEqual(86400, service.step)

    def test__calls__maybe_make_stats_request(self):
        service = stats.StatsService()
        self.assertEqual(
            (service.maybe_make_stats_request, (), {}),
            service.call)

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
            Config.objects.set_config('enable_analytics', True)

        service = stats.StatsService()
        maybe_make_stats_request = asynchronous(
            service.maybe_make_stats_request)
        maybe_make_stats_request().wait(5)

        self.assertThat(mock_call, MockCalledOnce())

    def test_maybe_make_stats_request_doesnt_make_request(self):
        mock_call = self.patch(stats, "make_maas_user_agent_request")

        with transaction.atomic():
            Config.objects.set_config('enable_analytics', False)

        service = stats.StatsService()
        maybe_make_stats_request = asynchronous(
            service.maybe_make_stats_request)
        maybe_make_stats_request().wait(5)

        self.assertThat(mock_call, MockNotCalled())
