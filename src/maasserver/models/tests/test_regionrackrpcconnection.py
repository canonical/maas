# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `RegionRackRPCConnection`."""

import random

from django.core.exceptions import ValidationError

from maasserver.models.regioncontrollerprocess import RegionControllerProcess
from maasserver.models.regioncontrollerprocessendpoint import (
    RegionControllerProcessEndpoint,
)
from maasserver.models.regionrackrpcconnection import RegionRackRPCConnection
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestRegionRackRPCConnection(MAASServerTestCase):
    """Tests for the `RegionRackRPCConnection` model."""

    def test_endpoint_rack_controller_are_unique(self):
        region = factory.make_RegionController()
        pid = random.randint(1, 5000)
        process = RegionControllerProcess.objects.create(
            pid=pid, region=region
        )
        address = factory.make_ip_address()
        port = random.randint(1, 5000)
        endpoint = RegionControllerProcessEndpoint.objects.create(
            process=process, address=address, port=port
        )
        rack_controller = factory.make_RackController()
        RegionRackRPCConnection.objects.create(
            endpoint=endpoint, rack_controller=rack_controller
        )
        self.assertRaises(
            ValidationError,
            RegionRackRPCConnection.objects.create,
            endpoint=endpoint,
            rack_controller=rack_controller,
        )
