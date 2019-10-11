# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test for :py:mod:`maasserver.clusterrpc.power`."""

__all__ = []

import random
from unittest.mock import Mock, sentinel

from crochet import wait_for
from maasserver.clusterrpc import pods as pods_module
from maasserver.clusterrpc.pods import (
    compose_machine,
    decompose_machine,
    discover_pod,
    get_best_discovered_result,
)
from maasserver.exceptions import PodProblem
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.pod import DiscoveredPod, DiscoveredPodHints
from provisioningserver.rpc.cluster import ComposeMachine, DecomposeMachine
from provisioningserver.rpc.exceptions import PodActionFail, UnknownPodType
from testtools.matchers import Equals, Is, IsInstance, MatchesAny, MatchesDict
from twisted.internet import reactor
from twisted.internet.defer import (
    CancelledError,
    fail,
    inlineCallbacks,
    succeed,
)
from twisted.internet.task import deferLater


wait_for_reactor = wait_for(30)  # 30 seconds.


class TestDiscoverPod(MAASTransactionServerTestCase):
    """Tests for `discover_pod`."""

    @wait_for_reactor
    @inlineCallbacks
    def test__calls_DiscoverPod_on_all_clients(self):
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
        self.assertEquals(
            ({rack_id: pod for rack_id in rack_ids}, {}), discovered
        )

    @wait_for_reactor
    @inlineCallbacks
    def test__returns_discovered_pod_and_errors(self):
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
        client.return_value = succeed({"pod": pod})
        clients.append(client)

        self.patch(pods_module, "getAllClients").return_value = clients
        discovered = yield discover_pod(pod_type, {})
        self.assertEquals(
            ({valid_rack_id: pod}, {error_rack_id: exception}), discovered
        )

    @wait_for_reactor
    @inlineCallbacks
    def test__handles_timeout(self):
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
        self.assertThat(discovered[0], Equals({}))
        self.assertThat(
            discovered[1], MatchesDict({rack_id: IsInstance(CancelledError)})
        )


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


class TestComposeMachine(MAASServerTestCase):
    """Tests for `compose_machine`."""

    def test__calls_and_returns_correctly(self):
        pod = factory.make_Pod()
        client = Mock()
        client.return_value = succeed(
            {"machine": sentinel.machine, "hints": sentinel.hints}
        )

        machine, hints = wait_for_reactor(compose_machine)(
            client,
            pod.power_type,
            pod.power_parameters,
            sentinel.request,
            pod.id,
            pod.name,
        )

        self.assertThat(
            client,
            MockCalledOnceWith(
                ComposeMachine,
                type=pod.power_type,
                context=pod.power_parameters,
                request=sentinel.request,
                pod_id=pod.id,
                name=pod.name,
            ),
        )
        self.assertEqual(sentinel.machine, machine)
        self.assertEqual(sentinel.hints, hints)

    def test__raises_PodProblem_for_UnknownPodType(self):
        pod = factory.make_Pod()
        client = Mock()
        client.return_value = fail(UnknownPodType(pod.power_type))

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(compose_machine),
            client,
            pod.power_type,
            pod.power_parameters,
            sentinel.request,
            pod.id,
            pod.name,
        )
        self.assertEqual(
            "Unable to compose machine because '%s' is an "
            "unknown pod type." % pod.power_type,
            str(error),
        )

    def test__raises_PodProblem_for_NotImplementedError(self):
        pod = factory.make_Pod()
        client = Mock()
        client.return_value = fail(NotImplementedError())

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(compose_machine),
            client,
            pod.power_type,
            pod.power_parameters,
            sentinel.request,
            pod.id,
            pod.name,
        )
        self.assertEqual(
            "Unable to compose machine because '%s' driver does not "
            "implement the 'compose' method." % pod.power_type,
            str(error),
        )

    def test__raises_PodProblem_for_PodActionFail(self):
        pod = factory.make_Pod()
        error_msg = factory.make_name("error")
        client = Mock()
        client.return_value = fail(PodActionFail(error_msg))

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(compose_machine),
            client,
            pod.power_type,
            pod.power_parameters,
            sentinel.request,
            pod.id,
            pod.name,
        )
        self.assertEqual(
            "Unable to compose machine because: %s" % error_msg, str(error)
        )

    def test__raises_same_exception(self):
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
            pod.power_parameters,
            sentinel.request,
            pod.id,
            pod.name,
        )
        self.assertEqual(exception_msg, str(error))


class TestDecomposeMachine(MAASServerTestCase):
    """Tests for `decompose_machine`."""

    def test__calls_and_returns_correctly(self):
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
            client, pod.power_type, pod.power_parameters, pod.id, pod.name
        )

        self.assertThat(
            client,
            MockCalledOnceWith(
                DecomposeMachine,
                type=pod.power_type,
                context=pod.power_parameters,
                pod_id=pod.id,
                name=pod.name,
            ),
        )
        self.assertEqual(hints, result)

    def test__raises_PodProblem_for_UnknownPodType(self):
        pod = factory.make_Pod()
        client = Mock()
        client.return_value = fail(UnknownPodType(pod.power_type))

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(decompose_machine),
            client,
            pod.power_type,
            pod.power_parameters,
            pod.id,
            pod.name,
        )
        self.assertEqual(
            "Unable to decompose machine because '%s' is an "
            "unknown pod type." % pod.power_type,
            str(error),
        )

    def test__raises_PodProblem_for_NotImplementedError(self):
        pod = factory.make_Pod()
        client = Mock()
        client.return_value = fail(NotImplementedError())

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(decompose_machine),
            client,
            pod.power_type,
            pod.power_parameters,
            pod.id,
            pod.name,
        )
        self.assertEqual(
            "Unable to decompose machine because '%s' driver does not "
            "implement the 'decompose' method." % pod.power_type,
            str(error),
        )

    def test__raises_PodProblem_for_PodActionFail(self):
        pod = factory.make_Pod()
        error_msg = factory.make_name("error")
        client = Mock()
        client.return_value = fail(PodActionFail(error_msg))

        error = self.assertRaises(
            PodProblem,
            wait_for_reactor(decompose_machine),
            client,
            pod.power_type,
            pod.power_parameters,
            pod.id,
            pod.name,
        )
        self.assertEqual(
            "Unable to decompose machine because: %s" % error_msg, str(error)
        )

    def test__raises_same_exception(self):
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
            pod.power_parameters,
            pod.id,
            pod.name,
        )
        self.assertEqual(exception_msg, str(error))
