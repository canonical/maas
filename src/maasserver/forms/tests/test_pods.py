# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for pod forms."""

__all__ = []

import random
from unittest.mock import (
    call,
    MagicMock,
)

import crochet
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from maasserver.enum import (
    BMC_TYPE,
    NODE_CREATION_TYPE,
)
from maasserver.exceptions import PodProblem
from maasserver.forms import pods as pods_module
from maasserver.forms.pods import (
    ComposeMachineForm,
    ComposeMachineForPodsForm,
    PodForm,
)
from maasserver.models.bmc import Pod
from maasserver.models.node import Machine
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import reload_object
from maasserver.utils.threads import deferToDatabase
from maastesting.matchers import (
    MockCalledOnce,
    MockCallsMatch,
    MockNotCalled,
)
from provisioningserver.drivers.pod import (
    Capabilities,
    DiscoveredMachine,
    DiscoveredPod,
    DiscoveredPodHints,
    RequestedMachine,
    RequestedMachineBlockDevice,
    RequestedMachineInterface,
)
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    Is,
    IsInstance,
    MatchesAll,
    MatchesListwise,
    MatchesSetwise,
    MatchesStructure,
    Not,
)
from twisted.internet.defer import (
    fail,
    inlineCallbacks,
    succeed,
)


wait_for_reactor = crochet.wait_for(30)  # 30 seconds.


def make_pod_with_hints():
    architectures = [
        "amd64/generic", "i386/generic", "arm64/generic",
        "armhf/generic"
    ]
    pod = factory.make_Pod(architectures=architectures)
    pod.hints.cores = random.randint(8, 16)
    pod.hints.memory = random.randint(4096, 8192)
    pod.hints.cpu_speed = random.randint(2000, 3000)
    pod.hints.save()
    return pod


class TestPodForm(MAASTransactionServerTestCase):

    def make_pod_info(self):
        # Use virsh pod type as the required fields are specific to the
        # type of pod being created.
        pod_type = 'virsh'
        pod_ip_adddress = factory.make_ipv4_address()
        pod_power_address = 'qemu+ssh://user@%s/system' % pod_ip_adddress
        pod_password = factory.make_name('password')
        return {
            'type': pod_type,
            'power_address': pod_power_address,
            'power_pass': pod_password,
            'ip_address': pod_ip_adddress,
        }

    def fake_pod_discovery(self):
        discovered_pod = DiscoveredPod(
            architectures=['amd64/generic'],
            cores=random.randint(2, 4), memory=random.randint(1024, 4096),
            local_storage=random.randint(1024, 1024 * 1024),
            cpu_speed=random.randint(2048, 4048),
            hints=DiscoveredPodHints(
                cores=random.randint(2, 4), memory=random.randint(1024, 4096),
                local_storage=random.randint(1024, 1024 * 1024),
                cpu_speed=random.randint(2048, 4048)))
        discovered_rack_1 = factory.make_RackController()
        discovered_rack_2 = factory.make_RackController()
        failed_rack = factory.make_RackController()
        self.patch(pods_module, "discover_pod").return_value = ({
            discovered_rack_1.system_id: discovered_pod,
            discovered_rack_2.system_id: discovered_pod,
        }, {
            failed_rack.system_id: factory.make_exception(),
        })
        return (
            discovered_pod,
            [discovered_rack_1, discovered_rack_2],
            [failed_rack])

    def test_contains_limited_set_of_fields(self):
        form = PodForm()
        self.assertItemsEqual(
            [
                'name',
                'type',
            ], list(form.fields))

    def test_creates_pod_with_discovered_information(self):
        discovered_pod, discovered_racks, failed_racks = (
            self.fake_pod_discovery())
        pod_info = self.make_pod_info()
        request = MagicMock()
        request.user = factory.make_User()
        form = PodForm(data=pod_info, request=request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertThat(pod, MatchesStructure(
            architectures=Equals(['amd64/generic']),
            name=MatchesAll(Not(Is(None)), Not(Equals(''))),
            cores=Equals(discovered_pod.cores),
            memory=Equals(discovered_pod.memory),
            cpu_speed=Equals(discovered_pod.cpu_speed),
            power_type=Equals(pod_info['type']),
            power_parameters=Equals({
                'power_address': pod_info['power_address'],
                'power_pass': pod_info['power_pass'],
            }),
            ip_address=MatchesStructure(ip=Equals(pod_info['ip_address'])),
        ))
        routable_racks = [
            relation.rack_controller
            for relation in pod.routable_rack_relationships.all()
            if relation.routable
        ]
        not_routable_racks = [
            relation.rack_controller
            for relation in pod.routable_rack_relationships.all()
            if not relation.routable
        ]
        self.assertItemsEqual(routable_racks, discovered_racks)
        self.assertItemsEqual(not_routable_racks, failed_racks)

    def test_creates_pod_with_name(self):
        discovered_pod, discovered_racks, failed_racks = (
            self.fake_pod_discovery())
        pod_info = self.make_pod_info()
        request = MagicMock()
        request.user = factory.make_User()
        pod_name = factory.make_name('pod')
        pod_info['name'] = pod_name
        form = PodForm(data=pod_info, request=request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertThat(pod, MatchesStructure(
            architectures=Equals(['amd64/generic']),
            name=Equals(pod_name),
            cores=Equals(discovered_pod.cores),
            memory=Equals(discovered_pod.memory),
            cpu_speed=Equals(discovered_pod.cpu_speed),
            power_type=Equals(pod_info['type']),
            power_parameters=Equals({
                'power_address': pod_info['power_address'],
                'power_pass': pod_info['power_pass'],
            }),
            ip_address=MatchesStructure(ip=Equals(pod_info['ip_address'])),
        ))

    @wait_for_reactor
    @inlineCallbacks
    def test_creates_pod_with_discovered_information_in_twisted(self):
        discovered_pod, discovered_racks, failed_racks = yield deferToDatabase(
            self.fake_pod_discovery)
        pods_module.discover_pod.return_value = succeed(
            pods_module.discover_pod.return_value)
        pod_info = self.make_pod_info()
        request = MagicMock()
        request.user = yield deferToDatabase(factory.make_User)
        form = yield deferToDatabase(PodForm, data=pod_info, request=request)
        is_valid = yield deferToDatabase(form.is_valid)
        self.assertTrue(is_valid, form._errors)
        pod = yield form.save()
        self.assertThat(pod, MatchesStructure(
            architectures=Equals(['amd64/generic']),
            name=MatchesAll(Not(Is(None)), Not(Equals(''))),
            cores=Equals(discovered_pod.cores),
            memory=Equals(discovered_pod.memory),
            cpu_speed=Equals(discovered_pod.cpu_speed),
            power_type=Equals(pod_info['type']),
            power_parameters=Equals({
                'power_address': pod_info['power_address'],
                'power_pass': pod_info['power_pass'],
            }),
            ip_address=MatchesStructure(ip=Equals(pod_info['ip_address'])),
        ))

        def validate_rack_routes():
            routable_racks = [
                relation.rack_controller
                for relation in pod.routable_rack_relationships.all()
                if relation.routable
            ]
            not_routable_racks = [
                relation.rack_controller
                for relation in pod.routable_rack_relationships.all()
                if not relation.routable
            ]
            self.assertItemsEqual(routable_racks, discovered_racks)
            self.assertItemsEqual(not_routable_racks, failed_racks)

        yield deferToDatabase(validate_rack_routes)

    @wait_for_reactor
    @inlineCallbacks
    def test_creates_pod_with_name_in_twisted(self):
        discovered_pod, discovered_racks, failed_racks = yield deferToDatabase(
            self.fake_pod_discovery)
        pods_module.discover_pod.return_value = succeed(
            pods_module.discover_pod.return_value)
        pod_info = self.make_pod_info()
        pod_name = factory.make_name('pod')
        pod_info['name'] = pod_name
        request = MagicMock()
        request.user = yield deferToDatabase(factory.make_User)
        form = yield deferToDatabase(PodForm, data=pod_info, request=request)
        is_valid = yield deferToDatabase(form.is_valid)
        self.assertTrue(is_valid, form._errors)
        pod = yield form.save()
        self.assertThat(pod, MatchesStructure(
            architectures=Equals(['amd64/generic']),
            name=Equals(pod_name),
            cores=Equals(discovered_pod.cores),
            memory=Equals(discovered_pod.memory),
            cpu_speed=Equals(discovered_pod.cpu_speed),
            power_type=Equals(pod_info['type']),
            power_parameters=Equals({
                'power_address': pod_info['power_address'],
                'power_pass': pod_info['power_pass'],
            }),
            ip_address=MatchesStructure(ip=Equals(pod_info['ip_address'])),
        ))

    @wait_for_reactor
    @inlineCallbacks
    def test_doesnt_create_pod_when_discovery_fails_in_twisted(self):
        discovered_pod, discovered_racks, failed_racks = yield deferToDatabase(
            self.fake_pod_discovery)
        pods_module.discover_pod.return_value = fail(factory.make_exception())
        pod_info = self.make_pod_info()
        request = MagicMock()
        request.user = yield deferToDatabase(factory.make_User)
        form = yield deferToDatabase(PodForm, data=pod_info, request=request)
        is_valid = yield deferToDatabase(form.is_valid)
        self.assertTrue(is_valid, form._errors)
        with ExpectedException(PodProblem):
            yield form.save()

        def validate_no_pods():
            self.assertItemsEqual([], Pod.objects.all())

        yield deferToDatabase(validate_no_pods)

    def test_prevents_duplicate_pod(self):
        discovered_pod, _, _ = self.fake_pod_discovery()
        pod_info = self.make_pod_info()
        request = MagicMock()
        request.user = factory.make_User()
        form = PodForm(data=pod_info, request=request)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        new_form = PodForm(data=pod_info)
        self.assertTrue(new_form.is_valid(), form._errors)
        self.assertRaises(ValidationError, new_form.save)

    def test_takes_over_bmc_with_pod(self):
        discovered_pod, _, _ = self.fake_pod_discovery()
        pod_info = self.make_pod_info()
        bmc = factory.make_BMC(
            power_type=pod_info['type'], power_parameters={
                'power_address': pod_info['power_address'],
                'power_pass': pod_info['power_pass'],
            })
        request = MagicMock()
        request.user = factory.make_User()
        form = PodForm(data=pod_info, request=request)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertEquals(bmc.id, pod.id)
        self.assertEquals(BMC_TYPE.POD, reload_object(bmc).bmc_type)

    def test_updates_existing_pod(self):
        discovered_pod, discovered_racks, failed_racks = (
            self.fake_pod_discovery())
        pod_info = self.make_pod_info()
        orig_pod = factory.make_Pod(pod_type=pod_info['type'])
        new_name = factory.make_name("pod")
        pod_info['name'] = new_name
        request = MagicMock()
        request.user = factory.make_User()
        form = PodForm(data=pod_info, request=request, instance=orig_pod)
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertThat(pod, MatchesStructure(
            id=Equals(orig_pod.id),
            bmc_type=Equals(BMC_TYPE.POD),
            architectures=Equals(['amd64/generic']),
            name=Equals(new_name),
            cores=Equals(discovered_pod.cores),
            memory=Equals(discovered_pod.memory),
            cpu_speed=Equals(discovered_pod.cpu_speed),
            power_type=Equals(pod_info['type']),
            power_parameters=Equals({
                'power_address': pod_info['power_address'],
                'power_pass': pod_info['power_pass'],
            }),
            ip_address=MatchesStructure(ip=Equals(pod_info['ip_address'])),
        ))
        routable_racks = [
            relation.rack_controller
            for relation in pod.routable_rack_relationships.all()
            if relation.routable
        ]
        not_routable_racks = [
            relation.rack_controller
            for relation in pod.routable_rack_relationships.all()
            if not relation.routable
        ]
        self.assertItemsEqual(routable_racks, discovered_racks)
        self.assertItemsEqual(not_routable_racks, failed_racks)

    @wait_for_reactor
    @inlineCallbacks
    def test_updates_existing_pod_in_twisted(self):
        discovered_pod, discovered_racks, failed_racks = yield deferToDatabase(
            self.fake_pod_discovery)
        pods_module.discover_pod.return_value = succeed(
            pods_module.discover_pod.return_value)
        pod_info = self.make_pod_info()
        orig_pod = yield deferToDatabase(
            factory.make_Pod, pod_type=pod_info['type'])
        new_name = factory.make_name("pod")
        pod_info['name'] = new_name
        request = MagicMock()
        request.user = yield deferToDatabase(factory.make_User)
        form = yield deferToDatabase(
            PodForm, data=pod_info, request=request, instance=orig_pod)
        is_valid = yield deferToDatabase(form.is_valid)
        self.assertTrue(is_valid, form._errors)
        pod = yield form.save()
        self.assertThat(pod, MatchesStructure(
            id=Equals(orig_pod.id),
            bmc_type=Equals(BMC_TYPE.POD),
            architectures=Equals(['amd64/generic']),
            name=Equals(new_name),
            cores=Equals(discovered_pod.cores),
            memory=Equals(discovered_pod.memory),
            cpu_speed=Equals(discovered_pod.cpu_speed),
            power_type=Equals(pod_info['type']),
            power_parameters=Equals({
                'power_address': pod_info['power_address'],
                'power_pass': pod_info['power_pass'],
            }),
            ip_address=MatchesStructure(ip=Equals(pod_info['ip_address'])),
        ))

        def validate_rack_routes():
            routable_racks = [
                relation.rack_controller
                for relation in pod.routable_rack_relationships.all()
                if relation.routable
            ]
            not_routable_racks = [
                relation.rack_controller
                for relation in pod.routable_rack_relationships.all()
                if not relation.routable
            ]
            self.assertItemsEqual(routable_racks, discovered_racks)
            self.assertItemsEqual(not_routable_racks, failed_racks)

        yield deferToDatabase(validate_rack_routes)

    def test_discover_and_sync_existing_pod(self):
        discovered_pod, discovered_racks, failed_racks = (
            self.fake_pod_discovery())
        pod_info = self.make_pod_info()
        orig_pod = factory.make_Pod(pod_type=pod_info['type'])
        request = MagicMock()
        request.user = factory.make_User()
        form = PodForm(data=pod_info, request=request, instance=orig_pod)
        pod = form.discover_and_sync_pod()
        self.assertThat(pod, MatchesStructure(
            id=Equals(orig_pod.id),
            bmc_type=Equals(BMC_TYPE.POD),
            architectures=Equals(['amd64/generic']),
            name=Equals(orig_pod.name),
            cores=Equals(discovered_pod.cores),
            memory=Equals(discovered_pod.memory),
            cpu_speed=Equals(discovered_pod.cpu_speed),
            power_type=Equals(pod_info['type']),
            power_parameters=Equals({}),
            ip_address=Is(None),
        ))
        routable_racks = [
            relation.rack_controller
            for relation in pod.routable_rack_relationships.all()
            if relation.routable
        ]
        not_routable_racks = [
            relation.rack_controller
            for relation in pod.routable_rack_relationships.all()
            if not relation.routable
        ]
        self.assertItemsEqual(routable_racks, discovered_racks)
        self.assertItemsEqual(not_routable_racks, failed_racks)

    @wait_for_reactor
    @inlineCallbacks
    def test_discover_and_sync_existing_pod_in_twisted(self):
        discovered_pod, discovered_racks, failed_racks = yield deferToDatabase(
            self.fake_pod_discovery)
        pods_module.discover_pod.return_value = succeed(
            pods_module.discover_pod.return_value)
        pod_info = self.make_pod_info()
        orig_pod = yield deferToDatabase(
            factory.make_Pod, pod_type=pod_info['type'])
        request = MagicMock()
        request.user = yield deferToDatabase(factory.make_User)
        form = yield deferToDatabase(
            PodForm, data=pod_info, request=request, instance=orig_pod)
        pod = yield form.discover_and_sync_pod()
        self.assertThat(pod, MatchesStructure(
            id=Equals(orig_pod.id),
            bmc_type=Equals(BMC_TYPE.POD),
            architectures=Equals(['amd64/generic']),
            name=Equals(orig_pod.name),
            cores=Equals(discovered_pod.cores),
            memory=Equals(discovered_pod.memory),
            cpu_speed=Equals(discovered_pod.cpu_speed),
            power_type=Equals(pod_info['type']),
            power_parameters=Equals({}),
            ip_address=Is(None),
        ))

        def validate_rack_routes():
            routable_racks = [
                relation.rack_controller
                for relation in pod.routable_rack_relationships.all()
                if relation.routable
            ]
            not_routable_racks = [
                relation.rack_controller
                for relation in pod.routable_rack_relationships.all()
                if not relation.routable
            ]
            self.assertItemsEqual(routable_racks, discovered_racks)
            self.assertItemsEqual(not_routable_racks, failed_racks)

        yield deferToDatabase(validate_rack_routes)

    def test_raises_unable_to_discover_because_no_racks(self):
        self.patch(pods_module, "discover_pod").return_value = ({}, {})
        form = PodForm(data=self.make_pod_info())
        self.assertTrue(form.is_valid(), form._errors)
        error = self.assertRaises(PodProblem, form.save)
        self.assertEquals(
            "Unable to start the pod discovery process. "
            "No rack controllers connected.", str(error))

    @wait_for_reactor
    @inlineCallbacks
    def test_raises_unable_to_discover_because_no_racks_in_twisted(self):
        self.patch(pods_module, "discover_pod").return_value = succeed(
            ({}, {}))
        form = yield deferToDatabase(PodForm, data=self.make_pod_info())
        is_valid = yield deferToDatabase(form.is_valid)
        self.assertTrue(is_valid, form._errors)

        def validate_error(failure):
            self.assertIsInstance(failure.value, PodProblem)
            self.assertEquals(
                "Unable to start the pod discovery process. "
                "No rack controllers connected.",
                str(failure.value))

        d = form.save()
        d.addErrback(validate_error)
        yield d

    def test_raises_exception_from_rack_controller(self):
        failed_rack = factory.make_RackController()
        exc = factory.make_exception()
        self.patch(pods_module, "discover_pod").return_value = ({}, {
            failed_rack.system_id: exc,
        })
        form = PodForm(data=self.make_pod_info())
        self.assertTrue(form.is_valid(), form._errors)
        error = self.assertRaises(PodProblem, form.save)
        self.assertEquals(str(exc), str(error))

    @wait_for_reactor
    @inlineCallbacks
    def test_raises_exception_from_rack_controller_in_twisted(self):
        failed_rack = yield deferToDatabase(factory.make_RackController)
        exc = factory.make_exception()
        self.patch(pods_module, "discover_pod").return_value = succeed(({}, {
            failed_rack.system_id: exc,
        }))
        form = yield deferToDatabase(PodForm, data=self.make_pod_info())
        is_valid = yield deferToDatabase(form.is_valid)
        self.assertTrue(is_valid, form._errors)

        def validate_error(failure):
            self.assertIsInstance(failure.value, PodProblem)
            self.assertEquals(str(exc), str(failure.value))

        d = form.save()
        d.addErrback(validate_error)
        yield d


class TestComposeMachineForm(MAASTransactionServerTestCase):

    def make_compose_machine_result(self, pod):
        composed_machine = DiscoveredMachine(
            hostname=factory.make_name('hostname'),
            architecture=pod.architectures[0],
            cores=1, memory=1024, cpu_speed=300,
            block_devices=[], interfaces=[])
        pod_hints = DiscoveredPodHints(
            cores=random.randint(0, 10), memory=random.randint(1024, 4096),
            cpu_speed=random.randint(1000, 3000), local_storage=0)
        return composed_machine, pod_hints

    def test__requires_request_kwarg(self):
        error = self.assertRaises(ValueError, ComposeMachineForm)
        self.assertEqual("'request' kwargs is required.", str(error))

    def test__requires_pod_kwarg(self):
        request = MagicMock()
        error = self.assertRaises(
            ValueError, ComposeMachineForm, request=request)
        self.assertEqual("'pod' kwargs is required.", str(error))

    def test__sets_up_fields_based_on_pod(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        form = ComposeMachineForm(request=request, pod=pod)
        self.assertThat(form.fields['cores'], MatchesStructure(
            required=Equals(False),
            validators=MatchesSetwise(
                MatchesAll(
                    IsInstance(MaxValueValidator),
                    MatchesStructure(limit_value=Equals(pod.hints.cores))),
                MatchesAll(
                    IsInstance(MinValueValidator),
                    MatchesStructure(limit_value=Equals(1))))))
        self.assertThat(form.fields['memory'], MatchesStructure(
            required=Equals(False),
            validators=MatchesSetwise(
                MatchesAll(
                    IsInstance(MaxValueValidator),
                    MatchesStructure(limit_value=Equals(pod.hints.memory))),
                MatchesAll(
                    IsInstance(MinValueValidator),
                    MatchesStructure(limit_value=Equals(1024))))))
        self.assertThat(form.fields['architecture'], MatchesStructure(
            required=Equals(False),
            choices=MatchesSetwise(*[
                Equals((architecture, architecture))
                for architecture in pod.architectures
            ])))
        self.assertThat(form.fields['cpu_speed'], MatchesStructure(
            required=Equals(False),
            validators=MatchesSetwise(
                MatchesAll(
                    IsInstance(MaxValueValidator),
                    MatchesStructure(limit_value=Equals(pod.hints.cpu_speed))),
                MatchesAll(
                    IsInstance(MinValueValidator),
                    MatchesStructure(limit_value=Equals(300))))))

    def test__sets_up_fields_based_on_pod_no_max_cpu_speed(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        pod.hints.cpu_speed = 0
        pod.save()
        form = ComposeMachineForm(request=request, pod=pod)
        self.assertThat(form.fields['cpu_speed'], MatchesStructure(
            required=Equals(False),
            validators=MatchesSetwise(
                MatchesAll(
                    IsInstance(MinValueValidator),
                    MatchesStructure(limit_value=Equals(300))))))

    def test__get_requested_machine_uses_all_initial_values(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        request_machine = form.get_requested_machine()
        self.assertThat(request_machine, MatchesAll(
            IsInstance(RequestedMachine),
            MatchesStructure(
                architecture=Equals(pod.architectures[0]),
                cores=Equals(1),
                memory=Equals(1024),
                cpu_speed=Is(None),
                block_devices=MatchesListwise([
                    MatchesAll(
                        IsInstance(RequestedMachineBlockDevice),
                        MatchesStructure(size=Equals(8 * (1000 ** 3))))]),
                interfaces=MatchesListwise([
                    IsInstance(RequestedMachineInterface)]))))

    def test__get_requested_machine_uses_passed_values(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        architecture = random.choice(pod.architectures)
        cores = random.randint(1, pod.hints.cores)
        memory = random.randint(1024, pod.hints.memory)
        cpu_speed = random.randint(300, pod.hints.cpu_speed)
        disk_1 = random.randint(8, 16) * (1000 ** 3)
        disk_1_tags = [
            factory.make_name('tag')
            for _ in range(3)
        ]
        disk_2 = random.randint(8, 16) * (1000 ** 3)
        disk_2_tags = [
            factory.make_name('tag')
            for _ in range(3)
        ]
        storage = 'root:%d(%s),extra:%d(%s)' % (
            disk_1 // (1000 ** 3), ','.join(disk_1_tags),
            disk_2 // (1000 ** 3), ','.join(disk_2_tags))
        form = ComposeMachineForm(data={
            'architecture': architecture,
            'cores': cores,
            'memory': memory,
            'cpu_speed': cpu_speed,
            'storage': storage,
        }, request=request, pod=pod)
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine()
        self.assertThat(request_machine, MatchesAll(
            IsInstance(RequestedMachine),
            MatchesStructure(
                architecture=Equals(architecture),
                cores=Equals(cores),
                memory=Equals(memory),
                cpu_speed=Equals(cpu_speed),
                block_devices=MatchesListwise([
                    MatchesAll(
                        IsInstance(RequestedMachineBlockDevice),
                        MatchesStructure(
                            size=Equals(disk_1), tags=Equals(disk_1_tags))),
                    MatchesAll(
                        IsInstance(RequestedMachineBlockDevice),
                        MatchesStructure(
                            size=Equals(disk_2), tags=Equals(disk_2_tags))),
                    ]),
                interfaces=MatchesListwise([
                    IsInstance(RequestedMachineInterface)]))))

    def test__get_requested_machine_handles_no_tags_in_storage(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        disk_1 = random.randint(8, 16) * (1000 ** 3)
        disk_2 = random.randint(8, 16) * (1000 ** 3)
        storage = 'root:%d,extra:%d' % (
            disk_1 // (1000 ** 3),
            disk_2 // (1000 ** 3))
        form = ComposeMachineForm(data={
            'storage': storage,
        }, request=request, pod=pod)
        self.assertTrue(form.is_valid(), form.errors)
        request_machine = form.get_requested_machine()
        self.assertThat(request_machine, MatchesAll(
            IsInstance(RequestedMachine),
            MatchesStructure(
                block_devices=MatchesListwise([
                    MatchesAll(
                        IsInstance(RequestedMachineBlockDevice),
                        MatchesStructure(
                            size=Equals(disk_1), tags=Equals([]))),
                    MatchesAll(
                        IsInstance(RequestedMachineBlockDevice),
                        MatchesStructure(
                            size=Equals(disk_2), tags=Equals([]))),
                    ]))))

    def test__save_raises_AttributeError(self):
        request = MagicMock()
        pod = make_pod_with_hints()
        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        self.assertRaises(AttributeError, form.save)

    def test__compose_with_commissioning(self):
        request = MagicMock()
        pod = make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints))

        # Mock start_commissioning so it doesn't use post commit hooks.
        mock_commissioning = self.patch(Machine, "start_commissioning")

        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        created_machine = form.compose()
        self.assertThat(created_machine, MatchesAll(
            IsInstance(Machine),
            MatchesStructure(
                cpu_count=Equals(1),
                memory=Equals(1024),
                cpu_speed=Equals(300))))
        self.assertThat(mock_commissioning, MockCalledOnce())

    def test__compose_duplicated_hostname(self):
        factory.make_Node(hostname='test')

        request = MagicMock()
        pod = make_pod_with_hints()

        form = ComposeMachineForm(
            data={'hostname': 'test'}, request=request, pod=pod)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {'hostname': ['Node with hostname "test" already exists']},
            form.errors)

    def test__compose_without_commissioning(self):
        request = MagicMock()
        pod = make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints))

        # Mock start_commissioning so it doesn't use post commit hooks.
        mock_commissioning = self.patch(Machine, "start_commissioning")

        form = ComposeMachineForm(
            data={"skip_commissioning": 'true'}, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        created_machine = form.compose()
        self.assertThat(created_machine, MatchesAll(
            IsInstance(Machine),
            MatchesStructure(
                cpu_count=Equals(1),
                memory=Equals(1024),
                cpu_speed=Equals(300))))
        self.assertThat(mock_commissioning, MockNotCalled())

    def test__compose_with_skip_commissioning_passed(self):
        request = MagicMock()
        pod = make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints))

        # Mock start_commissioning so it doesn't use post commit hooks.
        mock_commissioning = self.patch(Machine, "start_commissioning")

        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        created_machine = form.compose(skip_commissioning=True)
        self.assertThat(created_machine, MatchesAll(
            IsInstance(Machine),
            MatchesStructure(
                cpu_count=Equals(1),
                memory=Equals(1024),
                cpu_speed=Equals(300))))
        self.assertThat(mock_commissioning, MockNotCalled())

    def test__compose_sets_domain_and_zone(self):
        request = MagicMock()
        pod = make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints))

        domain = factory.make_Domain()
        zone = factory.make_Zone()
        form = ComposeMachineForm(data={
            "domain": domain.id,
            "zone": zone.id,
            "skip_commissioning": 'true',
        }, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        created_machine = form.compose()
        self.assertThat(created_machine, MatchesAll(
            IsInstance(Machine),
            MatchesStructure(
                domain=Equals(domain),
                zone=Equals(zone))))

    def test__compose_handles_timeout_error(self):
        request = MagicMock()
        pod = make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        client.side_effect = crochet.TimeoutError()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        error = self.assertRaises(PodProblem, form.compose)
        self.assertEquals(
            "Unable to compose a machine because '%s' driver timed out "
            "after 120 seconds." % pod.power_type, str(error))

    @wait_for_reactor
    @inlineCallbacks
    def test__compose_with_commissioning_in_reactor(self):
        request = MagicMock()
        pod = yield deferToDatabase(make_pod_with_hints)

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods_module, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods_module, "compose_machine")
        mock_compose_machine.return_value = succeed(
            (composed_machine, pod_hints))

        # Mock start_commissioning so it doesn't use post commit hooks.
        mock_commissioning = self.patch(Machine, "start_commissioning")

        form = yield deferToDatabase(
            ComposeMachineForm, data={}, request=request, pod=pod)
        is_valid = yield deferToDatabase(form.is_valid)
        self.assertTrue(is_valid)
        created_machine = yield form.compose()
        self.assertThat(created_machine, MatchesAll(
            IsInstance(Machine),
            MatchesStructure(
                cpu_count=Equals(1),
                memory=Equals(1024),
                cpu_speed=Equals(300))))
        self.assertThat(mock_commissioning, MockCalledOnce())


class TestComposeMachineForPodsForm(MAASServerTestCase):

    def make_data(self, pods):
        return {
            "cores": random.randint(
                1, min([pod.hints.cores for pod in pods])),
            "memory": random.randint(
                1024, min([pod.hints.memory for pod in pods])),
            "architecture": random.choice([
                "amd64/generic", "i386/generic",
                "arm64/generic", "armhf/generic"
            ])
        }

    def make_pods(self):
        return [
            make_pod_with_hints()
            for _ in range(3)
        ]

    def test__requires_request_kwarg(self):
        error = self.assertRaises(ValueError, ComposeMachineForPodsForm)
        self.assertEqual("'request' kwargs is required.", str(error))

    def test__requires_pods_kwarg(self):
        request = MagicMock()
        error = self.assertRaises(
            ValueError, ComposeMachineForPodsForm, request=request)
        self.assertEqual("'pods' kwargs is required.", str(error))

    def test__sets_up_pod_forms_based_on_pods(self):
        request = MagicMock()
        pods = self.make_pods()
        data = self.make_data(pods)
        form = ComposeMachineForPodsForm(request=request, data=data, pods=pods)
        self.assertTrue(form.is_valid())
        self.assertThat(form.pod_forms, MatchesListwise([
            MatchesAll(
                IsInstance(ComposeMachineForm),
                MatchesStructure(
                    request=Equals(request), data=Equals(data),
                    pod=Equals(pod)))
            for pod in pods
            ]))

    def test__save_raises_AttributeError(self):
        request = MagicMock()
        pods = self.make_pods()
        data = self.make_data(pods)
        form = ComposeMachineForPodsForm(request=request, data=data, pods=pods)
        self.assertTrue(form.is_valid())
        self.assertRaises(AttributeError, form.save)

    def test_compose_uses_non_commit_forms_first(self):
        request = MagicMock()
        pods = self.make_pods()
        # Make it skip the first over commitable pod
        pods[1].capabilities = [Capabilities.OVER_COMMIT]
        pods[1].save()
        data = self.make_data(pods)
        form = ComposeMachineForPodsForm(request=request, data=data, pods=pods)
        mock_form_compose = self.patch(ComposeMachineForm, 'compose')
        mock_form_compose.side_effect = [factory.make_exception(), None]
        self.assertTrue(form.is_valid())

        form.compose()
        self.assertThat(mock_form_compose, MockCallsMatch(
            call(
                skip_commissioning=True,
                creation_type=NODE_CREATION_TYPE.DYNAMIC),
            call(
                skip_commissioning=True,
                creation_type=NODE_CREATION_TYPE.DYNAMIC)))

    def test_compose_uses_commit_forms_second(self):
        request = MagicMock()
        pods = self.make_pods()
        # Make it skip all pods.
        for pod in pods:
            pod.capabilities = [Capabilities.OVER_COMMIT]
            pod.save()
        data = self.make_data(pods)
        form = ComposeMachineForPodsForm(request=request, data=data, pods=pods)
        mock_form_compose = self.patch(ComposeMachineForm, 'compose')
        mock_form_compose.side_effect = [
            factory.make_exception(), factory.make_exception(),
            factory.make_exception(), None]
        self.assertTrue(form.is_valid())

        form.compose()
        self.assertThat(mock_form_compose, MockCallsMatch(
            call(
                skip_commissioning=True,
                creation_type=NODE_CREATION_TYPE.DYNAMIC),
            call(
                skip_commissioning=True,
                creation_type=NODE_CREATION_TYPE.DYNAMIC),
            call(
                skip_commissioning=True,
                creation_type=NODE_CREATION_TYPE.DYNAMIC)))

    def test_clean_adds_error_for_no_matching_constraints(self):
        request = MagicMock()
        pods = self.make_pods()
        for pod in pods:
            pod.architectures = ["Not vaild architecture"]
            pod.save()
        data = self.make_data(pods)
        form = ComposeMachineForPodsForm(request=request, data=data, pods=pods)
        self.assertFalse(form.is_valid())
