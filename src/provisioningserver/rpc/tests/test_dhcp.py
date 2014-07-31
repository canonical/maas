# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.dhcp`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from fixtures import FakeLogger
from maastesting.factory import factory
from maastesting.matchers import MockCallsMatch
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    call,
    sentinel,
    )
from provisioningserver.omshell import Omshell
from provisioningserver.rpc import (
    dhcp,
    exceptions,
    )
from provisioningserver.utils import ExternalProcessError


class TestCreateHostMaps(MAASTestCase):

    def test_creates_omshell(self):
        omshell = self.patch(dhcp, "Omshell")
        dhcp.create_host_maps([], sentinel.shared_key)
        self.assertThat(omshell, MockCallsMatch(
            call(server_address=ANY, shared_key=sentinel.shared_key),
        ))

    def test_calls_omshell_create(self):
        omshell_create = self.patch(Omshell, "create")
        mappings = [
            {"ip_address": factory.getRandomIPAddress(),
             "mac_address": factory.getRandomMACAddress()}
            for _ in range(5)
        ]
        dhcp.create_host_maps(mappings, sentinel.shared_key)
        self.assertThat(omshell_create, MockCallsMatch(*(
            call(mapping["ip_address"], mapping["mac_address"])
            for mapping in mappings
        )))

    def test_raises_error_when_omshell_crashes(self):
        error_message = factory.make_name("error").encode("ascii")
        omshell_create = self.patch(Omshell, "create")
        omshell_create.side_effect = ExternalProcessError(
            returncode=2, cmd=("omshell",), output=error_message)
        ip_address = factory.getRandomIPAddress()
        mac_address = factory.getRandomMACAddress()
        mappings = [{"ip_address": ip_address, "mac_address": mac_address}]
        with FakeLogger("maas.dhcp") as logger:
            error = self.assertRaises(
                exceptions.CannotCreateHostMap, dhcp.create_host_maps,
                mappings, sentinel.shared_key)
        # The CannotCreateHostMap exception includes a message describing the
        # problematic mapping.
        self.assertDocTestMatches(
            "%s \u2192 %s: ..." % (mac_address, ip_address),
            unicode(error))
        # A message is also written to the maas.dhcp logger that describes the
        # problematic mapping.
        self.assertDocTestMatches(
            "Could not create host map for ... with address ...: ...",
            logger.output)
