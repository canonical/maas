# Copyright 2014-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from datetime import datetime
import http.client
from unittest import mock

from django.db import transaction
from django.urls import reverse
import prometheus_client
from twisted.application.internet import TimerService
from twisted.internet.defer import fail

from maasserver.enum import IPADDRESS_TYPE, IPRANGE_TYPE
from maasserver.models import Config
from maasserver.prometheus import stats
from maasserver.prometheus.stats import (
    push_stats_to_prometheus,
    STATS_DEFINITIONS,
    update_prometheus_stats,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting import get_testing_timeout
from maastesting.testcase import MAASTestCase
from maastesting.twisted import extract_result
from provisioningserver.events import EVENT_TYPES
from provisioningserver.prometheus.utils import create_metrics
from provisioningserver.utils.twisted import asynchronous

TIMEOUT = get_testing_timeout()


class TestPrometheusHandler(MAASServerTestCase):
    def test_prometheus_stats_handler_not_found_disabled(self):
        Config.objects.set_config("prometheus_enabled", False)
        response = self.client.get(reverse("metrics"))
        self.assertEqual("text/html; charset=utf-8", response["Content-Type"])
        self.assertEqual(response.status_code, http.client.NOT_FOUND)

    def test_prometheus_stats_handler_returns_success(self):
        Config.objects.set_config("prometheus_enabled", True)
        mock_prometheus_client = self.patch(stats, "prometheus_client")
        mock_prometheus_client.generate_latest.return_value = {}
        response = self.client.get(reverse("metrics"))
        self.assertEqual("text/plain", response["Content-Type"])
        self.assertEqual(response.status_code, http.client.OK)

    def test_prometheus_stats_handler_returns_metrics(self):
        Config.objects.set_config("prometheus_enabled", True)
        response = self.client.get(reverse("metrics"))
        content = response.content.decode("utf-8")
        metrics = (
            "maas_machines",
            "maas_nodes",
            "maas_net_spaces",
            "maas_net_fabrics",
            "maas_net_vlans",
            "maas_net_subnets_v4",
            "maas_net_subnets_v6",
            "maas_net_subnet_ip_count",
            "maas_net_subnet_ip_dynamic",
            "maas_net_subnet_ip_reserved",
            "maas_net_subnet_ip_static",
            "maas_service_availability",
            "maas_machines_total_mem",
            "maas_machines_total_cpu",
            "maas_machines_total_storage",
            "maas_machines_avg_deployment_time",
            "maas_service_availability",
            "maas_kvm_pods",
            "maas_kvm_machines",
            "maas_kvm_cores",
            "maas_kvm_memory",
            "maas_kvm_storage",
            "maas_kvm_overcommit_cores",
            "maas_kvm_overcommit_memory",
            "maas_machine_arches",
            "maas_custom_static_images_uploaded",
            "maas_custom_static_images_deployed",
            "maas_vmcluster_projects",
            "maas_vmcluster_hosts",
            "maas_vmcluster_vms",
        )
        for metric in metrics:
            self.assertIn(f"TYPE {metric} gauge", content)

    def test_prometheus_stats_handler_include_maas_id_label(self):
        self.patch(stats, "get_machines_by_architecture").return_value = {
            "amd64": 2,
            "i386": 1,
        }
        Config.objects.set_config("uuid", "abcde")
        Config.objects.set_config("prometheus_enabled", True)
        response = self.client.get(reverse("metrics"))
        content = response.content.decode("utf-8")
        for line in content.splitlines():
            if line.startswith("maas_"):
                self.assertIn('maas_id="abcde"', line)


class TestPrometheus(MAASServerTestCase):
    def test_update_prometheus_stats(self):
        self.patch(stats, "prometheus_client")
        # general values
        values = {
            "machine_status": {"random_status": 0},
            "controllers": {"regions": 0},
            "nodes": {"machines": 0},
            "network_stats": {"spaces": 0},
            "machine_stats": {"total_cpu": 0},
        }
        mock = self.patch(stats, "get_maas_stats")
        mock.return_value = values
        # architecture
        arches = {"amd64": 0, "i386": 0}
        mock_arches = self.patch(stats, "get_machines_by_architecture")
        mock_arches.return_value = arches
        vm_hosts = {
            "vm_hosts": 0,
            "vms": 0,
            "available_resources": {
                "cores": 10,
                "memory": 20,
                "storage": 30,
                "over_cores": 100,
                "over_memory": 200,
            },
            "utilized_resources": {
                "cores": 5,
                "memory": 10,
                "storage": 15,
            },
        }
        mock_vm_hosts = self.patch(stats, "get_vm_hosts_stats")
        mock_vm_hosts.return_value = vm_hosts
        subnet_stats = {
            "1.2.0.0/16": {
                "available": 2**16 - 3,
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
        }
        mock_subnet_stats = self.patch(stats, "get_subnets_utilisation_stats")
        mock_subnet_stats.return_value = subnet_stats
        metrics = create_metrics(
            STATS_DEFINITIONS, registry=prometheus_client.CollectorRegistry()
        )
        update_prometheus_stats(metrics)
        self.assertEqual(1, len(mock.mock_calls))
        self.assertEqual(1, len(mock_arches.mock_calls))
        self.assertEqual(1, len(mock_vm_hosts.mock_calls))
        self.assertEqual(1, len(mock_subnet_stats.mock_calls))

    def test_push_stats_to_prometheus(self):
        factory.make_RegionRackController()
        maas_name = "random.maas"
        push_gateway = "127.0.0.1:2000"
        mock_prometheus_client = self.patch(stats, "prometheus_client")
        push_stats_to_prometheus(maas_name, push_gateway)
        mock_prometheus_client.push_to_gateway.assert_called_once_with(
            push_gateway, job="stats_for_%s" % maas_name, registry=mock.ANY
        )

    def test_subnet_stats(self):
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
                ip=f"1.2.0.{n}",
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
                subnet=subnet,
            )
        for n in (80, 90, 100):
            factory.make_StaticIPAddress(
                ip=f"1.2.0.{n}",
                alloc_type=IPADDRESS_TYPE.STICKY,
                subnet=subnet,
            )
        metrics = create_metrics(
            STATS_DEFINITIONS, registry=prometheus_client.CollectorRegistry()
        )
        update_prometheus_stats(metrics)
        output = metrics.generate_latest().decode("ascii")
        self.assertIn(
            "maas_net_subnet_ip_count"
            '{cidr="1.2.0.0/16",status="available"} 65500.0',
            output,
        )
        self.assertIn(
            "maas_net_subnet_ip_count"
            '{cidr="1.2.0.0/16",status="unavailable"} 34.0',
            output,
        )
        self.assertIn(
            "maas_net_subnet_ip_dynamic"
            '{cidr="1.2.0.0/16",status="available"} 9.0',
            output,
        )
        self.assertIn(
            'maas_net_subnet_ip_dynamic{cidr="1.2.0.0/16",status="used"} 1.0',
            output,
        )
        self.assertIn(
            "maas_net_subnet_ip_reserved"
            '{cidr="1.2.0.0/16",status="available"} 18.0',
            output,
        )
        self.assertIn(
            'maas_net_subnet_ip_reserved{cidr="1.2.0.0/16",status="used"} 2.0',
            output,
        )
        self.assertIn(
            'maas_net_subnet_ip_static{cidr="1.2.0.0/16"} 3.0', output
        )

    def test_machine_avg_deployment_time_metric(self):
        """Test the average time of the last successful deployment of the
        machine in MAAS.
        """
        node_1 = factory.make_Node()
        node_2 = factory.make_Node()
        event_request_deployment = factory.make_EventType(
            EVENT_TYPES.REQUEST_NODE_START_DEPLOYMENT
        )
        event_deployed = factory.make_EventType(EVENT_TYPES.DEPLOYED)
        metrics = create_metrics(
            STATS_DEFINITIONS, registry=prometheus_client.CollectorRegistry()
        )

        # status: node_1 has never been deployed
        update_prometheus_stats(metrics)
        output = metrics.generate_latest().decode("ascii")
        self.assertIn(
            "maas_machines_avg_deployment_time NaN",
            output,
        )

        # status: node_1 starts its deployment for the first time (deployment
        # event never registered before)
        factory.make_Event(
            event_request_deployment,
            node_1,
            created=datetime.fromisoformat("2024-04-12T14:05:25"),
        )
        update_prometheus_stats(metrics)
        output = metrics.generate_latest().decode("ascii")
        self.assertIn(
            "maas_machines_avg_deployment_time NaN",
            output,
        )

        # status: node_1 finishes deployment
        factory.make_Event(
            event_deployed,
            node_1,
            created=datetime.fromisoformat("2024-04-12T14:10:37"),
        )
        update_prometheus_stats(metrics)
        output = metrics.generate_latest().decode("ascii")
        self.assertIn(
            "maas_machines_avg_deployment_time 312.0",
            output,
        )

        # status: node_1 starts deployment for the second time (current
        # deployment event belongs to the previous deployment)
        factory.make_Event(
            event_request_deployment,
            node_1,
            created=datetime.fromisoformat("2024-05-15T10:17:21"),
        )
        update_prometheus_stats(metrics)
        output = metrics.generate_latest().decode("ascii")
        self.assertIn(
            "maas_machines_avg_deployment_time NaN",
            output,
        )

        # status: node_1 finishes deployment for the second time
        factory.make_Event(
            event_deployed,
            node_1,
            created=datetime.fromisoformat("2024-05-15T10:20:25"),
        )
        update_prometheus_stats(metrics)
        output = metrics.generate_latest().decode("ascii")
        self.assertIn(
            "maas_machines_avg_deployment_time 184.0",
            output,
        )

        # status: node_2 starts its deployment for the first time
        factory.make_Event(
            event_request_deployment,
            node_2,
            created=datetime.fromisoformat("2024-05-15T10:25:40"),
        )
        update_prometheus_stats(metrics)
        output = metrics.generate_latest().decode("ascii")
        self.assertIn(
            "maas_machines_avg_deployment_time 184.0",
            output,
        )
        # status: node_2 finishes its deployment for the first time
        # The result is the average time of the deployments of node_1 and
        # node_2
        factory.make_Event(
            event_deployed,
            node_2,
            created=datetime.fromisoformat("2024-05-15T10:30:41"),
        )
        update_prometheus_stats(metrics)
        output = metrics.generate_latest().decode("ascii")
        self.assertIn(
            "maas_machines_avg_deployment_time 242.5",
            output,
        )


class TestPrometheusService(MAASTestCase):
    """Tests for `ImportPrometheusService`."""

    def test_is_a_TimerService(self):
        service = stats.PrometheusService()
        self.assertIsInstance(service, TimerService)

    def test_runs_once_an_hour_by_default(self):
        service = stats.PrometheusService()
        self.assertEqual(3600, service.step)

    def test_calls__maybe_make_stats_request(self):
        service = stats.PrometheusService()
        self.assertEqual(
            (service.maybe_push_prometheus_stats, (), {}), service.call
        )

    def test_maybe_make_stats_request_does_not_error(self):
        service = stats.PrometheusService()
        deferToDatabase = self.patch(stats, "deferToDatabase")
        exception_type = factory.make_exception_type()
        deferToDatabase.return_value = fail(exception_type())
        d = service.maybe_push_prometheus_stats()
        self.assertIsNone(extract_result(d))


class TestPrometheusServiceAsync(MAASTransactionServerTestCase):
    """Tests for the async parts of `PrometheusService`."""

    def test_maybe_make_stats_request_makes_request(self):
        mock_call = self.patch(stats, "push_stats_to_prometheus")

        with transaction.atomic():
            Config.objects.set_config("prometheus_enabled", True)
            Config.objects.set_config(
                "prometheus_push_gateway", "192.168.1.1:8081"
            )

        service = stats.PrometheusService()
        maybe_push_prometheus_stats = asynchronous(
            service.maybe_push_prometheus_stats
        )
        maybe_push_prometheus_stats().wait(TIMEOUT)

        mock_call.assert_called_once()

    def test_maybe_make_stats_request_doesnt_make_request(self):
        mock_prometheus_client = self.patch(stats, "prometheus_client")

        with transaction.atomic():
            Config.objects.set_config("enable_analytics", False)

        service = stats.PrometheusService()
        maybe_push_prometheus_stats = asynchronous(
            service.maybe_push_prometheus_stats
        )
        maybe_push_prometheus_stats().wait(TIMEOUT)
        mock_prometheus_client.push_stats_to_prometheus.assert_not_called()
