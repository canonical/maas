# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for pod forms."""

__all__ = []

import random
from unittest.mock import MagicMock

from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from maasserver.enum import BMC_TYPE
from maasserver.exceptions import PodProblem
from maasserver.forms import pods
from maasserver.forms.pods import (
    ComposeMachineForm,
    PodForm,
)
from maasserver.models.node import Machine
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maastesting.matchers import (
    MockCalledOnce,
    MockNotCalled,
)
from provisioningserver.drivers.pod import (
    DiscoveredMachine,
    DiscoveredPod,
    DiscoveredPodHints,
    RequestedMachine,
    RequestedMachineBlockDevice,
    RequestedMachineInterface,
)
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
from twisted.internet.defer import succeed


class TestPodForm(MAASServerTestCase):

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
        self.patch(pods, "discover_pod").return_value = ({
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

    def test_raises_unable_to_discover_because_no_racks(self):
        self.patch(pods, "discover_pod").return_value = ({}, {})
        form = PodForm(data=self.make_pod_info())
        self.assertTrue(form.is_valid(), form._errors)
        error = self.assertRaises(PodProblem, form.save)
        self.assertEquals(
            "No rack controllers connected to discover a pod.", str(error))

    def test_raises_exception_from_rack_controller(self):
        failed_rack = factory.make_RackController()
        exc = factory.make_exception()
        self.patch(pods, "discover_pod").return_value = ({}, {
            failed_rack.system_id: exc,
        })
        form = PodForm(data=self.make_pod_info())
        self.assertTrue(form.is_valid(), form._errors)
        error = self.assertRaises(PodProblem, form.save)
        self.assertEquals(str(exc), str(error))


class TestComposeMachineForm(MAASServerTestCase):

    def make_pod_with_hints(self):
        architectures = [
            "%s/%s" % (factory.make_name("arch"), factory.make_name("subarch"))
            for _ in range(3)
        ]
        cpu_speed = random.randint(2000, 3000)
        pod = factory.make_Pod(
            architectures=architectures, cpu_speed=cpu_speed)
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.save()
        return pod

    def make_compose_machine_result(self, pod):
        composed_machine = DiscoveredMachine(
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
        pod = self.make_pod_with_hints()
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
                    MatchesStructure(limit_value=Equals(pod.cpu_speed))),
                MatchesAll(
                    IsInstance(MinValueValidator),
                    MatchesStructure(limit_value=Equals(300))))))

    def test__sets_up_fields_based_on_pod_no_max_cpu_speed(self):
        request = MagicMock()
        pod = self.make_pod_with_hints()
        pod.cpu_speed = 0
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
        pod = self.make_pod_with_hints()
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
                        MatchesStructure(size=Equals(8 * (1024 ** 3))))]),
                interfaces=MatchesListwise([
                    IsInstance(RequestedMachineInterface)]))))

    def test__get_requested_machine_uses_passed_values(self):
        request = MagicMock()
        pod = self.make_pod_with_hints()
        architecture = random.choice(pod.architectures)
        cores = random.randint(1, pod.hints.cores)
        memory = random.randint(1024, pod.hints.memory)
        cpu_speed = random.randint(300, pod.cpu_speed)
        form = ComposeMachineForm(data={
            'architecture': architecture,
            'cores': cores,
            'memory': memory,
            'cpu_speed': cpu_speed,
        }, request=request, pod=pod)
        self.assertTrue(form.is_valid())
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
                        MatchesStructure(size=Equals(8 * (1024 ** 3))))]),
                interfaces=MatchesListwise([
                    IsInstance(RequestedMachineInterface)]))))

    def test__save_raises_AttributeError(self):
        request = MagicMock()
        pod = self.make_pod_with_hints()
        form = ComposeMachineForm(data={}, request=request, pod=pod)
        self.assertTrue(form.is_valid())
        self.assertRaises(AttributeError, form.save)

    def test__compose_with_commissioning(self):
        request = MagicMock()
        pod = self.make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods, "compose_machine")
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

    def test__compose_without_commissioning(self):
        request = MagicMock()
        pod = self.make_pod_with_hints()

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        composed_machine, pod_hints = self.make_compose_machine_result(pod)
        mock_compose_machine = self.patch(pods, "compose_machine")
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
