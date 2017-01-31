# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for pod forms."""

__all__ = []

import random
from unittest.mock import MagicMock

from django.core.exceptions import ValidationError
from maasserver import forms_pods
from maasserver.enum import BMC_TYPE
from maasserver.exceptions import PodProblem
from maasserver.forms_pods import PodForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from provisioningserver.drivers.pod import (
    DiscoveredPod,
    DiscoveredPodHints,
)
from testtools.matchers import (
    Equals,
    Is,
    MatchesAll,
    MatchesStructure,
    Not,
)


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
        self.patch(forms_pods, "discover_pod").return_value = ({
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
        self.patch(forms_pods, "discover_pod").return_value = ({}, {})
        form = PodForm(data=self.make_pod_info())
        self.assertTrue(form.is_valid(), form._errors)
        error = self.assertRaises(PodProblem, form.save)
        self.assertEquals(
            "No rack controllers connected to discover a pod.", str(error))

    def test_raises_exception_from_rack_controller(self):
        failed_rack = factory.make_RackController()
        exc = factory.make_exception()
        self.patch(forms_pods, "discover_pod").return_value = ({}, {
            failed_rack.system_id: exc,
        })
        form = PodForm(data=self.make_pod_info())
        self.assertTrue(form.is_valid(), form._errors)
        error = self.assertRaises(PodProblem, form.save)
        self.assertEquals(str(exc), str(error))
