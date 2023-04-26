# Copyright 2014-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test for :py:mod:`maasserver.clusterrpc.power`."""


import random
from unittest.mock import Mock, sentinel

from testtools.matchers import Is, IsInstance, MatchesAny, MatchesDict
from twisted.internet import reactor
from twisted.internet.defer import (
    CancelledError,
    fail,
    inlineCallbacks,
    succeed,
)
from twisted.internet.task import deferLater

from maasserver.clusterrpc import pods as pods_module
from maasserver.clusterrpc.pods import (
    compose_machine,
    decompose_machine,
    discover_pod,
    discover_pod_projects,
    get_best_discovered_result,
    send_pod_commissioning_results,
)
from maasserver.exceptions import PodProblem
from maasserver.models import NodeKey
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting.crochet import wait_for
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.pod import (
    DiscoveredCluster,
    DiscoveredPod,
    DiscoveredPodHints,
    DiscoveredPodProject,
)
from provisioningserver.rpc.cluster import (
    ComposeMachine,
    DecomposeMachine,
    SendPodCommissioningResults,
)
from provisioningserver.rpc.exceptions import PodActionFail, UnknownPodType

wait_for_reactor = wait_for()


class TestDiscoverPodProjects(MAASTransactionServerTestCase):
    @wait_for_reactor
    @inlineCallbacks
    def test_calls_DiscoverPodProjects_on_all_clients(self):
        rack_ids = [factory.make_name("system_id") for _ in range(3)]
        projects = [
            DiscoveredPodProject(name="p1", description="Project 1"),
            DiscoveredPodProject(name="p2", description="Project 2"),
        ]
        clients = []
        for rack_id in rack_ids:
            client = Mock()
            client.ident = rack_id
            client.return_value = succeed({"projects": projects})
            clients.append(client)

        self.patch(pods_module, "getAllClients").return_value = clients
        discovered = yield discover_pod_projects(factory.make_name("pod"), {})
        self.assertEqual(
            ({rack_id: projects for rack_id in rack_ids}, {}), discovered
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_returns_discovered_projects_and_errors(self):
        pod_type = factory.make_name("pod")
        projects = [
            DiscoveredPodProject(name="p1", description="Project 1"),
            DiscoveredPodProject(name="p2", description="Project 2"),
        ]

        clients = []
        client = Mock()
        error_rack_id = factory.make_name("system_id")
        client.ident = error_rack_id
        exception = UnknownPodType(pod_type)
        client.return_value = fail(exception)
        clients.append(client)

        valid_rack_id = factory.make_name("system_id")
        client = Mock()
        client.ident = valid_rack_id
        client.return_value = succeed({"projects": projects})
        clients.append(client)

        self.patch(pods_module, "getAllClients").return_value = clients
        discovered = yield discover_pod_projects(pod_type, {})
        self.assertEqual(
            ({valid_rack_id: projects}, {error_rack_id: exception}), discovered
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_handles_timeout(self):
        def defer_way_later(*args, **kwargs):
            # Create a defer that will finish in 1 minute.
            return deferLater(reactor, 60 * 60, lambda: None)

        rack_id = factory.make_name("system_id")
        client = Mock()
        client.ident = rack_id
        client.side_effect = defer_way_later

        self.patch(pods_module, "getAllClients").return_value = [client]
        discovered = yield discover_pod_projects(
            factory.make_name("pod"), {}, timeout=0.5
        )
        self.assertEqual({}, discovered[0])
        self.assertThat(
            discovered[1], MatchesDict({rack_id: IsInstance(CancelledError)})
        )


class TestDiscoverPod(MAASTransactionServerTestCase):
    """Tests for `discover_pod`."""

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_DiscoverPod_on_all_clients(self):
        rack_ids = [factory.make_name("system_id") for _ in range(3)]
        pod = DiscoveredPod(
            architectures=["amd64/generic"],
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 3000),
            memory=random.randint(1024, 4096),
            local_storage=random.randint(500, 1000),
            hints=DiscoveredPodHints(
                cores=random.randint(1, 8),
                cpu_speed=random.randint(1000, 3000),
                memory=random.randint(1024, 4096),
                local_storage=random.randint(500, 1000),
            ),
        )
        clients = []
        for rack_id in rack_ids:
            client = Mock()
            client.ident = rack_id
            client.return_value = succeed({"pod": pod})
            clients.append(client)

        self.patch(pods_module, "getAllClients").return_value = clients
        discovered = yield discover_pod(factory.make_name("pod"), {})
        self.assertEqual(
            ({rack_id: pod for rack_id in rack_ids}, {}), discovered
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_returns_discovered_pod_and_errors(self):
        pod_type = factory.make_name("pod")
        pod = DiscoveredPod(
            architectures=["amd64/generic"],
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 3000),
            memory=random.randint(1024, 4096),
            local_storage=random.randint(500, 1000),
            hints=DiscoveredPodHints(
                cores=random.randint(1, 8),
                cpu_speed=random.randint(1000, 3000),
                memory=random.randint(1024, 4096),
                local_storage=random.randint(500, 1000),
            ),
        )

        clients = []
        client = Mock()
        error_rack_id = factory.make_name("system_id")
        client.ident = error_rack_id
        exception = UnknownPodType(pod_type)
        client.return_value = fail(exception)
        clients.append(client)

        valid_rack_id = factory.make_name("system_id")
        client = Mock()
        client.ident = valid_rack_id
        client.return_value = succeed({"pod": pod, "cluster": None})
        clients.append(client)

        self.patch(pods_module, "getAllClients").return_value = clients
        discovered = yield discover_pod(pod_type, {})
        self.assertEqual(
            ({valid_rack_id: pod}, {error_rack_id: exception}), discovered
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_handles_timeout(self):
        def defer_way_later(*args, **kwargs):
            # Create a defer that will finish in 1 minute.
            return deferLater(reactor, 60 * 60, lambda: None)

        rack_id = factory.make_name("system_id")
        client = Mock()
        client.ident = rack_id
        client.side_effect = defer_way_later

        self.patch(pods_module, "getAllClients").return_value = [client]
        discovered = yield discover_pod(
            factory.make_name("pod"), {}, timeout=0.5
        )
        self.assertEqual({}, discovered[0])
        self.assertThat(
            discovered[1], MatchesDict({rack_id: IsInstance(CancelledError)})
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_discovers_cluster(self):
        rack_id = factory.make_name("system_id")
        client = Mock()
        client.ident = rack_id
        pod_type = factory.make_name("pod")
        cluster = DiscoveredCluster(
            name=factory.make_name("cluster"),
            project=factory.make_name("project"),
            pods=[
                DiscoveredPod(
                    architectures=["amd64/generic"],
                    cores=random.randint(1, 8),
                    cpu_speed=random.randint(1000, 3000),
                    memory=random.randint(1024, 4096),
                    local_storage=random.randint(500, 1000),
                    hints=DiscoveredPodHints(
                        cores=random.randint(1, 8),
                        cpu_speed=random.randint(1000, 3000),
                        memory=random.randint(1024, 4096),
                        local_storage=random.randint(500, 1000),
                    ),
                ),
                DiscoveredPod(
                    architectures=["amd64/generic"],
                    cores=random.randint(1, 8),
                    cpu_speed=random.randint(1000, 3000),
                    memory=random.randint(1024, 4096),
                    local_storage=random.randint(500, 1000),
                    hints=DiscoveredPodHints(
                        cores=random.randint(1, 8),
                        cpu_speed=random.randint(1000, 3000),
                        memory=random.randint(1024, 4096),
                        local_storage=random.randint(500, 1000),
                    ),
                ),
            ],
        )
        clients = []
        client.return_value = succeed({"cluster": cluster, "pod": None})
        clients.append(client)

        self.patch(pods_module, "getAllClients").return_value = clients

        discovered = yield discover_pod(pod_type, {})

        self.assertEqual(({rack_id: cluster}, {}), discovered)


class TestGetBestDiscoveredResult(MAASTestCase):
    def test_returns_one_of_the_discovered(self):
        self.assertThat(
            get_best_discovered_result(
                (
                    {
                        factory.make_name("system_id"): sentinel.first,
                        factory.make_name("system_id"): sentinel.second,
                    },
                    {},
                )
            ),
            MatchesAny(Is(sentinel.first), Is(sentinel.second)),
        )

    def test_returns_None(self):
        self.assertIsNone(get_best_discovered_result(({}, {})))

    def test_raises_unknown_exception(self):
        exc_type = factory.make_exception_type()
        self.assertRaises(
            exc_type,
            get_best_discovered_result,
            ({}, {factory.make_name("system_id"): exc_type()}),
        )

    def test_raises_UnknownPodType_over_unknown(self):
        exc_type = factory.make_exception_type()
        self.assertRaises(
            UnknownPodType,
            get_best_discovered_result,
            (
                {},
                {
                    factory.make_name("system_id"): exc_type(),
                    factory.make_name("system_id"): UnknownPodType("unknown"),
                },
            ),
        )

    def test_raises_NotImplemended_over_UnknownPodType(self):
        exc_type = factory.make_exception_type()
        self.assertRaises(
            NotImplementedError,
            get_best_discovered_result,
            (
                {},
                {
                    factory.make_name("system_id"): exc_type(),
                    factory.make_name("system_id"): UnknownPodType("unknown"),
                    factory.make_name("system_id"): NotImplementedError(),
                },
            ),
        )

    def test_raises_PodActionFail_over_NotImplemended(self):
        exc_type = factory.make_exception_type()
        self.assertRaises(
            PodActionFail,
            get_best_discovered_result,
            (
                {},
                {
                    factory.make_name("system_id"): exc_type(),
                    factory.make_name("system_id"): UnknownPodType("unknown"),
                    factory.make_name("system_id"): NotImplementedError(),
                    factory.make_name("system_id"): PodActionFail(),
                },
            ),
        )


class TestSendPodCommissioningResults(MAASServerTestCase):
    """Tests for `send_pod_commissioning_results`."""

    def test_calls_and_returns_correctly(self):
        pod = factory.make_Pod()
        node = factory.make_Node()
        token = NodeKey.objects.get_token_for_node(node)
        metadata_url = factory.make_url()
        client = Mock()
        client.return_value = succeed(None)

        wait_for_reactor(send_pod_commissioning_results)(
            client,
            pod.id,
            pod.name,
            pod.power_type,
            node.system_id,
            pod.get_power_parameters(),
            token.consumer.key,
            token.key,
            token.secret,
            metadata_url,
        )

        self.assertThat(
            client,
            MockCalledOnceWith(
                SendPodCommissioningResults,
                pod_id=pod.id,
                name=pod.name,
                type=pod.power_type,
                system_id=node.system_id,
                context=pod.get_power_parameters(),
                consumer_key=token.consumer.key,
                token_key=token.key,
                token_secret=token.secret,
                metadata_url=metadata_url,
            ),
        )

    def test_raises_PodProblem_for_UnknownPodType(self):
        pod = factory.make_Pod()
        node = factory.make_Node()
        token = NodeKey.objects.get_token_for_node(node)
        metadata_url = factory.make_url()
        client = Mock()
        client.return_value = fail(UnknownPodType(pod.power_type))

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(send_pod_commissioning_results),
            client,
            pod.id,
            pod.name,
            pod.power_type,
            node.system_id,
            pod.get_power_parameters(),
            token.consumer.key,
            token.key,
            token.secret,
            metadata_url,
        )
        self.assertEqual(
            f"Unable to send commissioning results for {pod.name}({pod.id}) "
            f"because `{pod.power_type}` is an unknown Pod type.",
            str(error),
        )

    def test_raises_PodProblem_for_NotImplementedError(self):
        pod = factory.make_Pod()
        node = factory.make_Node()
        token = NodeKey.objects.get_token_for_node(node)
        metadata_url = factory.make_url()
        client = Mock()
        client.return_value = fail(NotImplementedError())

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(send_pod_commissioning_results),
            client,
            pod.id,
            pod.name,
            pod.power_type,
            node.system_id,
            pod.get_power_parameters(),
            token.consumer.key,
            token.key,
            token.secret,
            metadata_url,
        )
        self.assertEqual(
            f"Unable to send commissioning results for {pod.name}({pod.id}) "
            f"because `{pod.power_type}` driver does not implement the "
            "'send_pod_commissioning_results' method.",
            str(error),
        )

    def test_raises_PodProblem_for_PodActionFail(self):
        pod = factory.make_Pod()
        node = factory.make_Node()
        token = NodeKey.objects.get_token_for_node(node)
        metadata_url = factory.make_url()
        error_msg = factory.make_name("error")
        client = Mock()
        client.return_value = fail(PodActionFail(error_msg))

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(send_pod_commissioning_results),
            client,
            pod.id,
            pod.name,
            pod.power_type,
            node.system_id,
            pod.get_power_parameters(),
            token.consumer.key,
            token.key,
            token.secret,
            metadata_url,
        )
        self.assertEqual(
            f"Unable to send commissioning results for {pod.name}({pod.id}) "
            f"because: {error_msg}",
            str(error),
        )

    def test_raises_same_exception(self):
        pod = factory.make_Pod()
        node = factory.make_Node()
        token = NodeKey.objects.get_token_for_node(node)
        metadata_url = factory.make_url()
        client = Mock()
        exception_type = factory.make_exception_type()
        exception_msg = factory.make_name("error")
        client.return_value = fail(exception_type(exception_msg))

        error = self.assertRaises(
            exception_type,
            wait_for_reactor(send_pod_commissioning_results),
            client,
            pod.id,
            pod.name,
            pod.power_type,
            node.system_id,
            pod.get_power_parameters(),
            token.consumer.key,
            token.key,
            token.secret,
            metadata_url,
        )
        self.assertEqual(exception_msg, str(error))


class TestComposeMachine(MAASServerTestCase):
    """Tests for `compose_machine`."""

    def test_calls_and_returns_correctly(self):
        pod = factory.make_Pod()
        client = Mock()
        client.return_value = succeed(
            {"machine": sentinel.machine, "hints": sentinel.hints}
        )

        machine, hints = wait_for_reactor(compose_machine)(
            client,
            pod.power_type,
            pod.get_power_parameters(),
            sentinel.request,
            pod.id,
            pod.name,
        )

        self.assertThat(
            client,
            MockCalledOnceWith(
                ComposeMachine,
                type=pod.power_type,
                context=pod.get_power_parameters(),
                request=sentinel.request,
                pod_id=pod.id,
                name=pod.name,
            ),
        )
        self.assertEqual(sentinel.machine, machine)
        self.assertEqual(sentinel.hints, hints)

    def test_raises_PodProblem_for_UnknownPodType(self):
        pod = factory.make_Pod()
        client = Mock()
        client.return_value = fail(UnknownPodType(pod.power_type))

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(compose_machine),
            client,
            pod.power_type,
            pod.get_power_parameters(),
            sentinel.request,
            pod.id,
            pod.name,
        )
        self.assertEqual(
            "Unable to compose machine because '%s' is an "
            "unknown pod type." % pod.power_type,
            str(error),
        )

    def test_raises_PodProblem_for_NotImplementedError(self):
        pod = factory.make_Pod()
        client = Mock()
        client.return_value = fail(NotImplementedError())

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(compose_machine),
            client,
            pod.power_type,
            pod.get_power_parameters(),
            sentinel.request,
            pod.id,
            pod.name,
        )
        self.assertEqual(
            "Unable to compose machine because '%s' driver does not "
            "implement the 'compose' method." % pod.power_type,
            str(error),
        )

    def test_raises_PodProblem_for_PodActionFail(self):
        pod = factory.make_Pod()
        error_msg = factory.make_name("error")
        client = Mock()
        client.return_value = fail(PodActionFail(error_msg))

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(compose_machine),
            client,
            pod.power_type,
            pod.get_power_parameters(),
            sentinel.request,
            pod.id,
            pod.name,
        )
        self.assertEqual(
            "Unable to compose machine because: %s" % error_msg, str(error)
        )

    def test_raises_same_exception(self):
        pod = factory.make_Pod()
        client = Mock()
        exception_type = factory.make_exception_type()
        exception_msg = factory.make_name("error")
        client.return_value = fail(exception_type(exception_msg))

        error = self.assertRaises(
            exception_type,
            wait_for_reactor(compose_machine),
            client,
            pod.power_type,
            pod.get_power_parameters(),
            sentinel.request,
            pod.id,
            pod.name,
        )
        self.assertEqual(exception_msg, str(error))


class TestDecomposeMachine(MAASServerTestCase):
    """Tests for `decompose_machine`."""

    def test_calls_and_returns_correctly(self):
        hints = DiscoveredPodHints(
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 2000),
            memory=random.randint(1024, 8192),
            local_storage=0,
        )
        pod = factory.make_Pod()
        client = Mock()
        client.return_value = succeed({"hints": hints})

        result = wait_for_reactor(decompose_machine)(
            client,
            pod.power_type,
            pod.get_power_parameters(),
            pod.id,
            pod.name,
        )

        self.assertThat(
            client,
            MockCalledOnceWith(
                DecomposeMachine,
                type=pod.power_type,
                context=pod.get_power_parameters(),
                pod_id=pod.id,
                name=pod.name,
            ),
        )
        self.assertEqual(hints, result)

    def test_raises_PodProblem_for_UnknownPodType(self):
        pod = factory.make_Pod()
        client = Mock()
        client.return_value = fail(UnknownPodType(pod.power_type))

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(decompose_machine),
            client,
            pod.power_type,
            pod.get_power_parameters(),
            pod.id,
            pod.name,
        )
        self.assertEqual(
            "Unable to decompose machine because '%s' is an "
            "unknown pod type." % pod.power_type,
            str(error),
        )

    def test_raises_PodProblem_for_NotImplementedError(self):
        pod = factory.make_Pod()
        client = Mock()
        client.return_value = fail(NotImplementedError())

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(decompose_machine),
            client,
            pod.power_type,
            pod.get_power_parameters(),
            pod.id,
            pod.name,
        )
        self.assertEqual(
            "Unable to decompose machine because '%s' driver does not "
            "implement the 'decompose' method." % pod.power_type,
            str(error),
        )

    def test_raises_PodProblem_for_PodActionFail(self):
        pod = factory.make_Pod()
        error_msg = factory.make_name("error")
        client = Mock()
        client.return_value = fail(PodActionFail(error_msg))

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(decompose_machine),
            client,
            pod.power_type,
            pod.get_power_parameters(),
            pod.id,
            pod.name,
        )
        self.assertEqual(
            "Unable to decompose machine because: %s" % error_msg, str(error)
        )

    def test_raises_same_exception(self):
        pod = factory.make_Pod()
        client = Mock()
        exception_type = factory.make_exception_type()
        exception_msg = factory.make_name("error")
        client.return_value = fail(exception_type(exception_msg))

        error = self.assertRaises(
            exception_type,
            wait_for_reactor(decompose_machine),
            client,
            pod.power_type,
            pod.get_power_parameters(),
            pod.id,
            pod.name,
        )
        self.assertEqual(exception_msg, str(error))
