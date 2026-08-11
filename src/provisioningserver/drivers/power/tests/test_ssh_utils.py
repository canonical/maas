#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.ssh_utils`."""

from unittest.mock import Mock

from paramiko import AutoAddPolicy, SSHClient

from maascommon.fips import FIPS_SSH_CONFIG, is_fips_enabled
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import ssh_utils as ssh_utils_module
from provisioningserver.drivers.power.ssh_utils import (
    connect_ssh_client,
    get_fips_transport_options,
    make_ssh_client,
    TrustedHostKeyPolicy,
)


def make_key_mock(name: str = "ssh-rsa", body: str = "AAAA") -> Mock:
    """Build a paramiko-like key Mock with byte-returning fingerprint."""
    key = Mock()
    key.get_name.return_value = name
    key.get_base64.return_value = body
    key.get_fingerprint.return_value = b"\x00" * 20
    return key


class TestGetFipsTransportOptions(MAASTestCase):
    """Behaviour of :func:`get_fips_transport_options`."""

    def test_returns_empty_dict_when_fips_disabled(self):
        if is_fips_enabled():
            self.skipTest("Running on a FIPS host")
        self.assertEqual(get_fips_transport_options(), {})

    def test_disabled_algorithms_keys_when_fips_enabled(self):
        original = ssh_utils_module.is_fips_enabled
        ssh_utils_module.is_fips_enabled = lambda: True
        try:
            options = get_fips_transport_options()
        finally:
            ssh_utils_module.is_fips_enabled = original

        self.assertIn("disabled_algorithms", options)
        disabled = options["disabled_algorithms"]
        for category in ("ciphers", "kex", "macs", "keys"):
            self.assertIn(category, disabled)
            self.assertIsInstance(disabled[category], list)
            for algo in disabled[category]:
                self.assertIsInstance(algo, str)

    def test_disabled_algorithms_excludes_fips_allowlist(self):
        # Verify that every FIPS-allowed algorithm is absent from the disabled
        # set.  We don't compare against paramiko private internals because
        # that would break on a paramiko upgrade unrelated to MAAS.
        original = ssh_utils_module.is_fips_enabled
        ssh_utils_module.is_fips_enabled = lambda: True
        try:
            options = get_fips_transport_options()
        finally:
            ssh_utils_module.is_fips_enabled = original

        disabled = options["disabled_algorithms"]
        for allowed in FIPS_SSH_CONFIG.ciphers:
            self.assertNotIn(
                allowed, disabled["ciphers"], f"{allowed} must not be disabled"
            )
        for allowed in FIPS_SSH_CONFIG.kex:
            self.assertNotIn(
                allowed, disabled["kex"], f"{allowed} must not be disabled"
            )
        for allowed in FIPS_SSH_CONFIG.macs:
            self.assertNotIn(
                allowed, disabled["macs"], f"{allowed} must not be disabled"
            )
        for allowed in FIPS_SSH_CONFIG.key_types:
            self.assertNotIn(
                allowed, disabled["keys"], f"{allowed} must not be disabled"
            )


class TestMakeSshClient(MAASTestCase):
    """Behaviour of :func:`make_ssh_client`."""

    def test_uses_autop_add_policy_on_non_fips_hosts(self):
        if is_fips_enabled():
            self.skipTest("Running on a FIPS host")
        client = make_ssh_client()
        try:
            self.assertIsInstance(client, SSHClient)
            self.assertIsInstance(client._policy, AutoAddPolicy)
        finally:
            client.close()

    def test_uses_trusted_policy_on_fips_hosts(self):
        original = ssh_utils_module.is_fips_enabled
        ssh_utils_module.is_fips_enabled = lambda: True
        try:
            client = make_ssh_client()
        finally:
            ssh_utils_module.is_fips_enabled = original
        try:
            self.assertIsInstance(client, SSHClient)
            self.assertIsInstance(client._policy, TrustedHostKeyPolicy)
        finally:
            client.close()


class TestConnectSshClient(MAASTestCase):
    """Behaviour of :func:`connect_ssh_client`."""

    def test_passes_address_user_pass_through(self):
        client = Mock(spec=SSHClient)
        if is_fips_enabled():
            self.skipTest("Running on a FIPS host")
        connect_ssh_client(
            client, power_address="host", power_user="user", power_pass="pw"
        )
        client.connect.assert_called_once_with(
            "host", username="user", password="pw"
        )

    def test_passes_disabled_algorithms_when_fips_enabled(self):
        client = Mock(spec=SSHClient)
        original = ssh_utils_module.is_fips_enabled
        ssh_utils_module.is_fips_enabled = lambda: True
        try:
            connect_ssh_client(
                client,
                power_address="host",
                power_user="user",
                power_pass="pw",
            )
        finally:
            ssh_utils_module.is_fips_enabled = original

        client.connect.assert_called_once()
        kwargs = client.connect.call_args.kwargs
        self.assertEqual(kwargs["username"], "user")
        self.assertEqual(kwargs["password"], "pw")
        self.assertIn("disabled_algorithms", kwargs)
        self.assertEqual(
            set(kwargs["disabled_algorithms"].keys()),
            {"ciphers", "kex", "macs", "keys"},
        )


class TestTrustedHostKeyPolicy(MAASTestCase):
    """Behaviour of :class:`TrustedHostKeyPolicy`."""

    def test_fail_open_accepts_unknown_host_key(self):
        policy = TrustedHostKeyPolicy(fail_open=True)
        client = Mock(spec=SSHClient)
        client._host_keys = Mock()
        key = make_key_mock()

        policy.missing_host_key(client, "host.example", key)
        client._host_keys.add.assert_called_once_with(
            "host.example", "ssh-rsa", key
        )

    def _patch_rpc(self, return_value=None, rpc_side_effect=None):
        """Patch RPC machinery and blockingCallFromThread for a test.

        ``blockingCallFromThread`` is patched to call its ``func`` argument
        directly (bypassing the Twisted reactor), so the mock RPC client is
        invoked as it would be in production without needing a live reactor.
        """
        if rpc_side_effect is not None:
            rpc_client = Mock(side_effect=rpc_side_effect)
        else:
            rpc_client = Mock(return_value=return_value)
        rpc_factory = Mock(return_value=rpc_client)
        command_token = object()

        blocking = self.patch(ssh_utils_module, "blockingCallFromThread")
        blocking.side_effect = lambda _reactor, func, *args, **kwargs: func(
            *args, **kwargs
        )

        original_factory = ssh_utils_module._rpc_client_factory
        original_command = ssh_utils_module._rpc_command
        ssh_utils_module._rpc_client_factory = rpc_factory
        ssh_utils_module._rpc_command = command_token
        self.addCleanup(
            setattr, ssh_utils_module, "_rpc_client_factory", original_factory
        )
        self.addCleanup(
            setattr, ssh_utils_module, "_rpc_command", original_command
        )
        return rpc_client, rpc_factory, command_token, blocking

    def test_rpc_trusted_adds_key(self):
        policy = TrustedHostKeyPolicy()
        client = Mock(spec=SSHClient)
        client._host_keys = Mock()
        key = make_key_mock()

        rpc_client, rpc_factory, command_token, blocking = self._patch_rpc(
            return_value={"verified": True}
        )

        policy.missing_host_key(client, "host.example", key)

        rpc_factory.assert_called_once_with()
        # blockingCallFromThread dispatches the RPC call in the reactor thread.
        blocking.assert_called_once()
        rpc_client.assert_called_once_with(
            command_token,
            host="host.example",
            key_type="ssh-rsa",
            public_key="AAAA",
        )
        client._host_keys.add.assert_called_once_with(
            "host.example", "ssh-rsa", key
        )

    def test_rpc_failure_rejects_host_key(self):
        from paramiko import SSHException

        policy = TrustedHostKeyPolicy()
        client = Mock(spec=SSHClient)
        client._host_keys = Mock()
        key = make_key_mock()

        self._patch_rpc(rpc_side_effect=RuntimeError("rpc down"))

        self.assertRaises(
            SSHException,
            policy.missing_host_key,
            client,
            "host.example",
            key,
        )
        client._host_keys.add.assert_not_called()

    def test_rpc_untrusted_rejects_host_key(self):
        from paramiko import SSHException

        policy = TrustedHostKeyPolicy()
        client = Mock(spec=SSHClient)
        client._host_keys = Mock()
        key = make_key_mock()

        self._patch_rpc(return_value={"verified": False})

        self.assertRaises(
            SSHException,
            policy.missing_host_key,
            client,
            "host.example",
            key,
        )
        client._host_keys.add.assert_not_called()
