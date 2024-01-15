# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `RegionControllerProcess`."""


import random

from django.core.exceptions import ValidationError

from maasserver.models.regioncontrollerprocess import RegionControllerProcess
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestRegionControllerProcess(MAASServerTestCase):
    """Tests for the `RegionControllerProcess` model."""

    def test_pid_and_region_are_unique(self):
        region = factory.make_RegionController()
        pid = random.randint(1, 5000)
        RegionControllerProcess.objects.create(pid=pid, region=region)
        self.assertRaises(
            ValidationError,
            RegionControllerProcess.objects.create,
            pid=pid,
            region=region,
        )
