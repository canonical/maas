# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Test the behaviour of bmc signals.

These signals are tested in src/maasserver/models/tests/test_bmc.py. They
handle cleaning up orphaned IPs after BMC model instance deletion.
"""

from maasserver.enum import BMC_TYPE
from maasserver.models.podhints import PodHints
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestCreatePodHints(MAASServerTestCase):
    def test_creates_hints_for_pod(self):
        pod = factory.make_Pod()
        self.assertIsNotNone(pod.hints)

    def test_creates_hints_bmc_converted_to_pod(self):
        bmc = factory.make_BMC()
        bmc.bmc_type = BMC_TYPE.POD
        bmc.save()
        self.assertIsNotNone(bmc.hints)

    def test_deletes_hints_when_chassis_converted_to_bmc(self):
        pod = factory.make_Pod()
        pod = pod.as_bmc()
        pod.bmc_type = BMC_TYPE.BMC
        pod.save()
        self.assertRaises(
            PodHints.DoesNotExist, lambda: reload_object(pod).hints
        )
