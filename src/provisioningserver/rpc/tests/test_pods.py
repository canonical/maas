# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.pod`."""


import json
import random
import re
from unittest.mock import call, MagicMock
from urllib.parse import urlparse

from testtools import ExpectedException
from twisted.internet.defer import fail, inlineCallbacks, returnValue, succeed

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.matchers import MockCallsMatch
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.pod import (
    DiscoveredCluster,
    DiscoveredMachine,
    DiscoveredPod,
    DiscoveredPodHints,
    DiscoveredPodProject,
    RequestedMachine,
    RequestedMachineBlockDevice,
    RequestedMachineInterface,
)
from provisioningserver.drivers.pod.registry import PodDriverRegistry
from provisioningserver.refresh.maas_api_helper import (
    Credentials,
    SignalException,
)
from provisioningserver.rpc import exceptions, pods

TIMEOUT = get_testing_timeout()


class TestDiscoverPodProjects(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    @inlineCallbacks
    def test_unknown_pod_raises_UnknownPodType(self):
        unknown_type = factory.make_name("unknown")
        with ExpectedException(exceptions.UnknownPodType):
            yield pods.discover_pod_projects(unknown_type, {})

    @inlineCallbacks
    def test_converts_exceptions(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.discover_projects.return_value = fail(Exception("fail!"))
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(exceptions.PodActionFail):
            yield pods.discover_pod_projects(fake_driver.name, {})

    @inlineCallbacks
    def test_return_projects(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        projects = [
            {"name": "p1", "description": "Project 1"},
            {"name": "p2", "description": "Project 2"},
        ]
        fake_driver.discover_projects.return_value = succeed(projects)
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        result = yield pods.discover_pod_projects(fake_driver.name, {})
        self.assertEqual(
            result,
            {
                "projects": [
                    DiscoveredPodProject(name="p1", description="Project 1"),
                    DiscoveredPodProject(name="p2", description="Project 2"),
                ]
            },
        )


class TestDiscoverPod(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    @inlineCallbacks
    def test_unknown_pod_raises_UnknownPodType(self):
        unknown_type = factory.make_name("unknown")
        with ExpectedException(exceptions.UnknownPodType):
            yield pods.discover_pod(unknown_type, {})

    @inlineCallbacks
    def test_handles_driver_not_returning_Deferred(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.discover.return_value = None
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape(
                "bad pod driver '%s'; 'discover' did not "
                "return Deferred." % fake_driver.name
            ),
        ):
            yield pods.discover_pod(fake_driver.name, {})

    @inlineCallbacks
    def test_handles_driver_resolving_to_None(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.discover.return_value = succeed(None)
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape("unable to discover pod information."),
        ):
            yield pods.discover_pod(fake_driver.name, {})

    @inlineCallbacks
    def test_handles_driver_not_resolving_to_DiscoveredPod(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.discover.return_value = succeed({})
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape(
                "bad pod driver '%s'; 'discover' returned "
                "invalid result." % fake_driver.name
            ),
        ):
            yield pods.discover_pod(fake_driver.name, {})

    @inlineCallbacks
    def test_handles_driver_resolving_to_DiscoveredPod(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        discovered_pod = DiscoveredPod(
            architectures=["amd64/generic"],
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 3000),
            memory=random.randint(1024, 8192),
            local_storage=0,
            hints=DiscoveredPodHints(
                cores=random.randint(1, 8),
                cpu_speed=random.randint(1000, 2000),
                memory=random.randint(1024, 8192),
                local_storage=0,
            ),
            machines=[],
        )
        fake_driver.discover.return_value = succeed(discovered_pod)
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        result = yield pods.discover_pod(fake_driver.name, {})
        self.assertEqual({"pod": discovered_pod}, result)

    @inlineCallbacks
    def test_handles_driver_raising_NotImplementedError(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.discover.return_value = fail(NotImplementedError())
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(NotImplementedError):
            yield pods.discover_pod(fake_driver.name, {})

    @inlineCallbacks
    def test_handles_driver_raising_any_Exception(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_exception_type = factory.make_exception_type()
        fake_exception_msg = factory.make_name("error")
        fake_exception = fake_exception_type(fake_exception_msg)
        fake_driver.discover.return_value = fail(fake_exception)
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape("Failed talking to pod: " + fake_exception_msg),
        ):
            yield pods.discover_pod(fake_driver.name, {})

    @inlineCallbacks
    def test_handlers_driver_returning_cluster(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        expected_cluster = DiscoveredCluster(
            name=factory.make_name("name"),
            project=factory.make_name("project"),
            pods=[
                DiscoveredPod(name=factory.make_name("pod-name"))
                for _ in range(0, 3)
            ],
        )
        fake_driver.discover.return_value = returnValue(expected_cluster)
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        result = yield pods.discover_pod(fake_driver.name, {})
        discovered_cluster = result["cluster"]
        self.assertEqual(expected_cluster.name, discovered_cluster.name)
        self.assertEqual(expected_cluster.project, discovered_cluster.project)
        self.assertCountEqual(expected_cluster.pods, discovered_cluster.pods)


class TestComposeMachine(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def make_requested_machine(self):
        return RequestedMachine(
            hostname=factory.make_name("hostname"),
            architecture="amd64/generic",
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 3000),
            memory=random.randint(1024, 8192),
            block_devices=[
                RequestedMachineBlockDevice(size=random.randint(8, 16))
            ],
            interfaces=[RequestedMachineInterface()],
        )

    @inlineCallbacks
    def test_unknown_pod_raises_UnknownPodType(self):
        unknown_type = factory.make_name("unknown")
        fake_request = self.make_requested_machine()
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        with ExpectedException(exceptions.UnknownPodType):
            yield pods.compose_machine(
                unknown_type, {}, fake_request, pod_id=pod_id, name=pod_name
            )

    @inlineCallbacks
    def test_handles_driver_not_returning_Deferred(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.compose.return_value = None
        fake_request = self.make_requested_machine()
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape(
                "bad pod driver '%s'; 'compose' did not "
                "return Deferred." % fake_driver.name
            ),
        ):
            yield pods.compose_machine(
                fake_driver.name,
                {},
                fake_request,
                pod_id=pod_id,
                name=pod_name,
            )

    @inlineCallbacks
    def test_handles_driver_resolving_to_None(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.compose.return_value = succeed(None)
        fake_request = self.make_requested_machine()
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(exceptions.PodInvalidResources):
            yield pods.compose_machine(
                fake_driver.name,
                {},
                fake_request,
                pod_id=pod_id,
                name=pod_name,
            )

    @inlineCallbacks
    def test_handles_driver_not_resolving_to_tuple(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.compose.return_value = succeed({})
        fake_request = self.make_requested_machine()
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape(
                "bad pod driver '%s'; 'compose' returned "
                "invalid result." % fake_driver.name
            ),
        ):
            yield pods.compose_machine(
                fake_driver.name,
                {},
                fake_request,
                pod_id=pod_id,
                name=pod_name,
            )

    @inlineCallbacks
    def test_handles_driver_not_resolving_to_tuple_of_discovered(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.compose.return_value = succeed((object(), object()))
        fake_request = self.make_requested_machine()
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape(
                "bad pod driver '%s'; 'compose' returned "
                "invalid result." % fake_driver.name
            ),
        ):
            yield pods.compose_machine(
                fake_driver.name,
                {},
                fake_request,
                pod_id=pod_id,
                name=pod_name,
            )

    @inlineCallbacks
    def test_handles_driver_resolving_to_tuple_of_discovered(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_request = self.make_requested_machine()
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        machine = DiscoveredMachine(
            hostname=factory.make_name("hostname"),
            architecture="amd64/generic",
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 3000),
            memory=random.randint(1024, 8192),
            block_devices=[],
            interfaces=[],
        )
        hints = DiscoveredPodHints(
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 2000),
            memory=random.randint(1024, 8192),
            local_storage=0,
        )
        fake_driver.compose.return_value = succeed((machine, hints))
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        result = yield pods.compose_machine(
            fake_driver.name, {}, fake_request, pod_id=pod_id, name=pod_name
        )
        self.assertEqual({"machine": machine, "hints": hints}, result)

    @inlineCallbacks
    def test_handles_driver_raising_NotImplementedError(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.compose.return_value = fail(NotImplementedError())
        fake_request = self.make_requested_machine()
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(NotImplementedError):
            yield pods.compose_machine(
                fake_driver.name,
                {},
                fake_request,
                pod_id=pod_id,
                name=pod_name,
            )

    @inlineCallbacks
    def test_handles_driver_raising_any_Exception(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_exception_type = factory.make_exception_type()
        fake_exception_msg = factory.make_name("error")
        fake_exception = fake_exception_type(fake_exception_msg)
        fake_driver.compose.return_value = fail(fake_exception)
        fake_request = self.make_requested_machine()
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape("Failed talking to pod: " + fake_exception_msg),
        ):
            yield pods.compose_machine(
                fake_driver.name,
                {},
                fake_request,
                pod_id=pod_id,
                name=pod_name,
            )


class TestSendPodCommissioningResults(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    @inlineCallbacks
    def test_unknown_pod_raises_UnknownPodType(self):
        with ExpectedException(exceptions.UnknownPodType):
            yield pods.send_pod_commissioning_results(
                pod_type=factory.make_name("type"),
                context={},
                pod_id=random.randint(1, 10),
                name=factory.make_name("name"),
                system_id=factory.make_name("system_id"),
                consumer_key=factory.make_name("consumer_key"),
                token_key=factory.make_name("token_key"),
                token_secret=factory.make_name("token_secret"),
                metadata_url=urlparse(factory.make_url()),
            )

    @inlineCallbacks
    def test_handles_driver_not_returning_Deferred(self):
        pod_type = factory.make_name("type")
        fake_driver = MagicMock()
        fake_driver.get_commissioning_data.return_value = None
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape(
                f"bad pod driver '{pod_type}'; 'get_commissioning_data' did not "
                "return Deferred."
            ),
        ):
            yield pods.send_pod_commissioning_results(
                pod_type=pod_type,
                context={},
                pod_id=random.randint(1, 10),
                name=factory.make_name("name"),
                system_id=factory.make_name("system_id"),
                consumer_key=factory.make_name("consumer_key"),
                token_key=factory.make_name("token_key"),
                token_secret=factory.make_name("token_secret"),
                metadata_url=urlparse(factory.make_url()),
            )

    @inlineCallbacks
    def test_sends_results(self):
        mock_signal = self.patch_autospec(pods, "signal")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        metadata_url = factory.make_url()
        filename1 = factory.make_name("filename1")
        data1 = {factory.make_name("key1"): factory.make_name("value1")}
        filename2 = factory.make_name("filename2")
        data2 = {factory.make_name("key2"): factory.make_name("value2")}
        fake_driver = MagicMock()
        fake_driver.get_commissioning_data.return_value = succeed(
            {filename1: data1, filename2: data2}
        )
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        ret = yield pods.send_pod_commissioning_results(
            pod_type=factory.make_name("type"),
            context={},
            pod_id=random.randint(1, 10),
            name=factory.make_name("name"),
            system_id=factory.make_name("system_id"),
            consumer_key=consumer_key,
            token_key=token_key,
            token_secret=token_secret,
            metadata_url=urlparse(metadata_url),
        )
        self.assertDictEqual({}, ret)
        self.assertThat(
            mock_signal,
            MockCallsMatch(
                call(
                    url=metadata_url,
                    credentials=Credentials(
                        consumer_key=consumer_key,
                        token_key=token_key,
                        token_secret=token_secret,
                    ),
                    status="WORKING",
                    files={
                        filename1: json.dumps(data1, indent=4).encode(),
                        f"{filename1}.out": json.dumps(
                            data1, indent=4
                        ).encode(),
                        f"{filename1}.err": b"",
                        f"{filename1}.yaml": b"",
                    },
                    exit_status=0,
                    error=f"Finished {filename1}: 0",
                ),
                call(
                    url=metadata_url,
                    credentials=Credentials(
                        consumer_key=consumer_key,
                        token_key=token_key,
                        token_secret=token_secret,
                    ),
                    status="WORKING",
                    files={
                        filename2: json.dumps(data2, indent=4).encode(),
                        f"{filename2}.out": json.dumps(
                            data2, indent=4
                        ).encode(),
                        f"{filename2}.err": b"",
                        f"{filename2}.yaml": b"",
                    },
                    exit_status=0,
                    error=f"Finished {filename2}: 0",
                ),
            ),
        )

    @inlineCallbacks
    def test_sends_results_raises_podactionfail_on_signalexception(self):
        mock_signal = self.patch_autospec(pods, "signal")
        err_msg = factory.make_name("error_message")
        mock_signal.side_effect = SignalException(err_msg)
        name = (factory.make_name("name"),)
        system_id = factory.make_name("system_id")
        fake_driver = MagicMock()
        fake_driver.get_commissioning_data.return_value = succeed(
            {factory.make_name("filename"): factory.make_name("data")}
        )
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape(
                f"Unable to send Pod commissioning information for {name}({system_id}): {err_msg}"
            ),
        ):
            yield pods.send_pod_commissioning_results(
                pod_type=factory.make_name("type"),
                context={},
                pod_id=random.randint(1, 10),
                name=name,
                system_id=system_id,
                consumer_key=factory.make_name("consumer_key"),
                token_key=factory.make_name("token_key"),
                token_secret=factory.make_name("token_secret"),
                metadata_url=urlparse(factory.make_url()),
            )

    @inlineCallbacks
    def test_handles_driver_raising_NotImplementedError(self):
        fake_driver = MagicMock()
        fake_driver.get_commissioning_data.return_value = fail(
            NotImplementedError()
        )
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(NotImplementedError):
            yield pods.send_pod_commissioning_results(
                pod_type=factory.make_name("type"),
                context={},
                pod_id=random.randint(1, 10),
                name=factory.make_name("name"),
                system_id=factory.make_name("system_id"),
                consumer_key=factory.make_name("consumer_key"),
                token_key=factory.make_name("token_key"),
                token_secret=factory.make_name("token_secret"),
                metadata_url=urlparse(factory.make_url()),
            )

    @inlineCallbacks
    def test_handles_driver_raising_any_Exception(self):
        fake_driver = MagicMock()
        fake_exception_type = factory.make_exception_type()
        fake_exception_msg = factory.make_name("error")
        fake_exception = fake_exception_type(fake_exception_msg)
        fake_driver.get_commissioning_data.return_value = fail(fake_exception)
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape("Failed talking to pod: " + fake_exception_msg),
        ):
            yield pods.send_pod_commissioning_results(
                pod_type=factory.make_name("type"),
                context={},
                pod_id=random.randint(1, 10),
                name=factory.make_name("name"),
                system_id=factory.make_name("system_id"),
                consumer_key=factory.make_name("consumer_key"),
                token_key=factory.make_name("token_key"),
                token_secret=factory.make_name("token_secret"),
                metadata_url=urlparse(factory.make_url()),
            )


class TestDecomposeMachine(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    @inlineCallbacks
    def test_unknown_pod_raises_UnknownPodType(self):
        unknown_type = factory.make_name("unknown")
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        with ExpectedException(exceptions.UnknownPodType):
            yield pods.decompose_machine(
                unknown_type, {}, pod_id=pod_id, name=pod_name
            )

    @inlineCallbacks
    def test_handles_driver_not_returning_Deferred(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.decompose.return_value = None
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape(
                "bad pod driver '%s'; 'decompose' did not "
                "return Deferred." % fake_driver.name
            ),
        ):
            yield pods.decompose_machine(
                fake_driver.name, {}, pod_id=pod_id, name=pod_name
            )

    @inlineCallbacks
    def test_handles_driver_returning_None(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.decompose.return_value = succeed(None)
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape(
                "bad pod driver '%s'; 'decompose' "
                "returned invalid result." % fake_driver.name
            ),
        ):
            yield pods.decompose_machine(
                fake_driver.name, {}, pod_id=pod_id, name=pod_name
            )

    @inlineCallbacks
    def test_handles_driver_not_returning_hints(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.decompose.return_value = succeed(object())
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape(
                "bad pod driver '%s'; 'decompose' "
                "returned invalid result." % fake_driver.name
            ),
        ):
            yield pods.decompose_machine(
                fake_driver.name, {}, pod_id=pod_id, name=pod_name
            )

    @inlineCallbacks
    def test_works_when_driver_returns_hints(self):
        hints = DiscoveredPodHints(
            cores=random.randint(1, 8),
            cpu_speed=random.randint(1000, 2000),
            memory=random.randint(1024, 8192),
            local_storage=0,
        )
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.decompose.return_value = succeed(hints)
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        result = yield pods.decompose_machine(
            fake_driver.name, {}, pod_id=pod_id, name=pod_name
        )
        self.assertEqual({"hints": hints}, result)

    @inlineCallbacks
    def test_handles_driver_raising_NotImplementedError(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_driver.decompose.return_value = fail(NotImplementedError())
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(NotImplementedError):
            yield pods.decompose_machine(
                fake_driver.name, {}, pod_id=pod_id, name=pod_name
            )

    @inlineCallbacks
    def test_handles_driver_raising_any_Exception(self):
        fake_driver = MagicMock()
        fake_driver.name = factory.make_name("pod")
        fake_exception_type = factory.make_exception_type()
        fake_exception_msg = factory.make_name("error")
        fake_exception = fake_exception_type(fake_exception_msg)
        fake_driver.decompose.return_value = fail(fake_exception)
        pod_id = random.randint(1, 10)
        pod_name = factory.make_name("pod")
        self.patch(PodDriverRegistry, "get_item").return_value = fake_driver
        with ExpectedException(
            exceptions.PodActionFail,
            re.escape("Failed talking to pod: " + fake_exception_msg),
        ):
            yield pods.decompose_machine(
                fake_driver.name, {}, pod_id=pod_id, name=pod_name
            )
