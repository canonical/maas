# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for pod forms."""

__all__ = []

import random

from maasserver import forms
from maasserver.clusterrpc.driver_parameters import (
    DriverType,
    get_driver_choices,
)
from maasserver.exceptions import PodProblem
from maasserver.forms import PodForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
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

    def test_contains_limited_set_of_fields(self):
        form = PodForm()
        self.assertItemsEqual(
            [
                'name',
                'type',
            ], list(form.fields))

    def test_creates_pod_with_discovered_information(self):
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
        self.patch(forms, "discover_pod").return_value = ({
            discovered_rack_1.system_id: discovered_pod,
            discovered_rack_2.system_id: discovered_pod,
        }, {
            failed_rack.system_id: factory.make_exception(),
        })
        pod_type = random.choice(
            get_driver_choices(driver_type=DriverType.pod))[0]
        form = PodForm(data={
            'type': pod_type,
        })
        self.assertTrue(form.is_valid(), form._errors)
        pod = form.save()
        self.assertThat(pod, MatchesStructure(
            architectures=Equals(['amd64/generic']),
            name=MatchesAll(Not(Is(None)), Not(Equals(''))),
            cores=Equals(discovered_pod.cores),
            memory=Equals(discovered_pod.memory),
            cpu_speed=Equals(discovered_pod.cpu_speed),
            power_type=Equals(pod_type),
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
        self.assertItemsEqual(
            routable_racks, [discovered_rack_1, discovered_rack_2])
        self.assertItemsEqual(not_routable_racks, [failed_rack])

    def test_raises_unable_to_discover_because_no_racks(self):
        self.patch(forms, "discover_pod").return_value = ({}, {})
        pod_type = random.choice(
            get_driver_choices(driver_type=DriverType.pod))[0]
        form = PodForm(data={
            'type': pod_type,
        })
        self.assertTrue(form.is_valid(), form._errors)
        error = self.assertRaises(PodProblem, form.save)
        self.assertEquals(
            "No rack controllers connected to discover a pod.", str(error))

    def test_raises_exception_from_rack_controller(self):
        failed_rack = factory.make_RackController()
        exc = factory.make_exception()
        self.patch(forms, "discover_pod").return_value = ({}, {
            failed_rack.system_id: exc,
        })
        pod_type = random.choice(
            get_driver_choices(driver_type=DriverType.pod))[0]
        form = PodForm(data={
            'type': pod_type,
        })
        self.assertTrue(form.is_valid(), form._errors)
        error = self.assertRaises(PodProblem, form.save)
        self.assertEquals(str(exc), str(error))
