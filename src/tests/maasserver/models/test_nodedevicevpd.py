# Copyright 2017-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver NodeDeviceVPD model."""

from django.core.exceptions import ValidationError

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestNodeDeviceVPD(MAASServerTestCase):
    def test_unique_on_nodedevice_and_key(self):
        # We can only ever have one NodeDeviceVPD object for a particular NodeDevice
        # and key.
        entry = factory.make_NodeDeviceVPD()
        self.assertRaises(
            ValidationError,
            factory.make_NodeDeviceVPD,
            node_device=entry.node_device,
            key=entry.key,
        )
