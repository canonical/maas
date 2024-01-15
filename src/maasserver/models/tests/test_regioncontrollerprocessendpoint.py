# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `RegionControllerProcessEndpoint`."""


import random

from django.core.exceptions import ValidationError

from maasserver.models.regioncontrollerprocess import RegionControllerProcess
from maasserver.models.regioncontrollerprocessendpoint import (
    RegionControllerProcessEndpoint,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestRegionControllerProcessEndpoint(MAASServerTestCase):
    """Tests for the `RegionControllerProcessEndpoint` model."""

    def test_process_address_port_are_unique(self):
        region = factory.make_RegionController()
        pid = random.randint(1, 5000)
        process = RegionControllerProcess.objects.create(
            pid=pid, region=region
        )
        address = factory.make_ip_address()
        port = random.randint(1, 5000)
        RegionControllerProcessEndpoint.objects.create(
            process=process, address=address, port=port
        )
        self.assertRaises(
            ValidationError,
            RegionControllerProcessEndpoint.objects.create,
            process=process,
            address=address,
            port=port,
        )
