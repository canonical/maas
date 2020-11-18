import base64
from unittest.mock import Mock

from maastesting.testcase import MAASTestCase
from provisioningserver.dhcp import omapi
from provisioningserver.dhcp.omapi import (
    generate_omapi_key,
    OMAPI_OP_STATUS,
    OMAPI_OP_UPDATE,
    OmapiClient,
    OmapiError,
    OmapiMessage,
)


class TestGenerateOmapiKey(MAASTestCase):
    def test_generate_key(self):
        key = generate_omapi_key()
        self.assertEqual(len(base64.decodebytes(key.encode("ascii"))), 64)


class TestOmapiClient(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.mock_omapi_cli = Mock()
        self.mock_omapi = self.patch(omapi, "Omapi")
        self.mock_omapi.return_value = self.mock_omapi_cli

    def test_initialize(self):
        OmapiClient("shared-key")
        self.mock_omapi.assert_called_once_with(
            "127.0.0.1", 7911, b"omapi_key", b"shared-key"
        )

    def test_initialize_ipv6(self):
        OmapiClient("shared-key", ipv6=True)
        self.mock_omapi.assert_called_once_with(
            "127.0.0.1", 7912, b"omapi_key", b"shared-key"
        )

    def test_add_host(self):
        cli = OmapiClient("shared-key")
        cli.add_host("aa:bb:cc:dd:ee:ff", "1.2.3.4")
        self.mock_omapi_cli.add_host_supersede.assert_called_once_with(
            "1.2.3.4", "aa:bb:cc:dd:ee:ff", b"aa-bb-cc-dd-ee-ff"
        )

    def test_remove_host(self):
        cli = OmapiClient("shared-key")
        cli.del_host("aa:bb:cc:dd:ee:ff")
        self.mock_omapi_cli.del_host("aa:bb:cc:dd:ee:ff")

    def test_update_host(self):
        self.mock_omapi_cli.query_server.side_effect = [
            OmapiMessage(opcode=OMAPI_OP_UPDATE),
            OmapiMessage(opcode=OMAPI_OP_STATUS),
        ]
        cli = OmapiClient("shared-key")
        cli.update_host("aa:bb:cc:dd:ee:ff", "1.2.3.4")
        # first call gets the existing entry by name
        self.assertEqual(
            self.mock_omapi_cli.query_server.mock_calls[0].args[0].obj,
            [(b"name", b"aa-bb-cc-dd-ee-ff")],
        )
        # second call updates the IP address
        self.assertEqual(
            self.mock_omapi_cli.query_server.mock_calls[1].args[0].obj,
            [(b"ip-address", b"\x01\x02\x03\x04")],
        )

    def test_update_host_not_found(self):
        # STATUS opcode signals an error in this case
        self.mock_omapi_cli.query_server.return_value = OmapiMessage(
            opcode=OMAPI_OP_STATUS
        )
        cli = OmapiClient("shared-key")
        err = self.assertRaises(
            OmapiError, cli.update_host, "aa:bb:cc:dd:ee:ff", "1.2.3.4"
        )
        self.assertEqual(str(err), "Host not found: aa-bb-cc-dd-ee-ff")

    def test_update_error(self):
        # returning the UPDATE opcode after an update makes it fail
        self.mock_omapi_cli.query_server.return_value = OmapiMessage(
            opcode=OMAPI_OP_UPDATE
        )
        cli = OmapiClient("shared-key")
        err = self.assertRaises(
            OmapiError, cli.update_host, "aa:bb:cc:dd:ee:ff", "1.2.3.4"
        )
        self.assertEqual(
            str(err),
            "Updating IP for host aa-bb-cc-dd-ee-ff to 1.2.3.4 failed",
        )
