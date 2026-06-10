#  Copyright 2026 Canonical Ltd.  This software is licensed under the GNU Affero General Public License version 3 (see the file LICENSE).

"""SSH FIPS enforcement tests for power drivers."""

from unittest.mock import MagicMock, patch

import pytest

from maascommon.fips import FIPS_SSH_CONFIG
from maascommon.logging.security import FIPS_CRYPTO_ERROR, FIPS_SSH_AUTH
from provisioningserver.drivers.power.utils import connect_ssh

_FIPS_SSH_KWARGS = {
    "ciphers": list(FIPS_SSH_CONFIG.ciphers),
    "kex": list(FIPS_SSH_CONFIG.kex),
    "macs": list(FIPS_SSH_CONFIG.macs),
    "key_types": list(FIPS_SSH_CONFIG.key_types),
}


def _make_ssh_client_mock(stdout_data: str = "ok") -> MagicMock:
    mock_stdout = MagicMock()
    mock_stdout.read.return_value = stdout_data.encode()

    mock_transport = MagicMock()
    mock_transport.local_cipher = "aes256-ctr"
    mock_transport.local_mac = "hmac-sha2-256"

    mock_host_key = MagicMock()
    mock_host_key.get_name.return_value = "ecdsa-sha2-nistp256"
    mock_transport.get_remote_server_key.return_value = mock_host_key

    mock_client = MagicMock()
    mock_client.exec_command.return_value = (
        MagicMock(),
        mock_stdout,
        MagicMock(),
    )
    mock_client.get_transport.return_value = mock_transport

    return mock_client


class TestConnectSSH:
    def test_uses_reject_policy_in_fips_mode(self) -> None:
        from paramiko import RejectPolicy

        mock_client = _make_ssh_client_mock()

        with (
            patch(
                "provisioningserver.drivers.power.utils.is_fips_enabled",
                return_value=True,
            ),
            patch(
                "provisioningserver.drivers.power.utils.SSHClient",
                return_value=mock_client,
            ),
            patch(
                "provisioningserver.drivers.power.utils.get_fips_ssh_config",
                return_value=_FIPS_SSH_KWARGS,
            ),
        ):
            connect_ssh("test-driver", "10.0.0.1", "admin", "secret")

        policy_arg = mock_client.set_missing_host_key_policy.call_args[0][0]
        assert isinstance(policy_arg, RejectPolicy)

    def test_uses_auto_add_policy_outside_fips_mode(self) -> None:
        from paramiko import AutoAddPolicy

        mock_client = _make_ssh_client_mock()

        with (
            patch(
                "provisioningserver.drivers.power.utils.is_fips_enabled",
                return_value=False,
            ),
            patch(
                "provisioningserver.drivers.power.utils.SSHClient",
                return_value=mock_client,
            ),
        ):
            connect_ssh("test-driver", "10.0.0.1", "admin", "secret")

        policy_arg = mock_client.set_missing_host_key_policy.call_args[0][0]
        assert isinstance(policy_arg, AutoAddPolicy)

    def test_passes_fips_ssh_config_in_fips_mode(self) -> None:
        mock_client = _make_ssh_client_mock()

        with (
            patch(
                "provisioningserver.drivers.power.utils.is_fips_enabled",
                return_value=True,
            ),
            patch(
                "provisioningserver.drivers.power.utils.SSHClient",
                return_value=mock_client,
            ),
            patch(
                "provisioningserver.drivers.power.utils.get_fips_ssh_config",
                return_value=_FIPS_SSH_KWARGS,
            ),
        ):
            connect_ssh("test-driver", "10.0.0.1", "admin", "secret")

        assert {
            k: v
            for k, v in mock_client.connect.call_args[1].items()
            if k in _FIPS_SSH_KWARGS
        } == _FIPS_SSH_KWARGS

    def test_no_fips_kwargs_outside_fips_mode(self) -> None:
        mock_client = _make_ssh_client_mock()

        with (
            patch(
                "provisioningserver.drivers.power.utils.is_fips_enabled",
                return_value=False,
            ),
            patch(
                "provisioningserver.drivers.power.utils.SSHClient",
                return_value=mock_client,
            ),
        ):
            connect_ssh("test-driver", "10.0.0.1", "admin", "secret")

        # In non-FIPS mode, no FIPS algorithm kwargs should be passed.
        connect_kwargs = mock_client.connect.call_args[1]
        for key in _FIPS_SSH_KWARGS:
            assert key not in connect_kwargs

    def test_emits_fips_ssh_auth_log_on_successful_connection(self) -> None:
        mock_client = _make_ssh_client_mock()

        with (
            patch(
                "provisioningserver.drivers.power.utils.is_fips_enabled",
                return_value=True,
            ),
            patch(
                "provisioningserver.drivers.power.utils.SSHClient",
                return_value=mock_client,
            ),
            patch(
                "provisioningserver.drivers.power.utils.get_fips_ssh_config",
                return_value=_FIPS_SSH_KWARGS,
            ),
            patch(
                "provisioningserver.drivers.power.utils.logger"
            ) as mock_logger,
        ):
            connect_ssh("test-driver", "10.0.0.1", "admin", "secret")

        mock_logger.info.assert_called_once()
        assert mock_logger.info.call_args[0][0] == FIPS_SSH_AUTH

    def test_emits_fips_crypto_error_log_on_ssh_failure(self) -> None:
        from paramiko import SSHException

        mock_client = MagicMock()
        mock_client.connect.side_effect = SSHException("negotiation failed")

        with (
            patch(
                "provisioningserver.drivers.power.utils.is_fips_enabled",
                return_value=True,
            ),
            patch(
                "provisioningserver.drivers.power.utils.SSHClient",
                return_value=mock_client,
            ),
            patch(
                "provisioningserver.drivers.power.utils.get_fips_ssh_config",
                return_value=_FIPS_SSH_KWARGS,
            ),
            patch(
                "provisioningserver.drivers.power.utils.logger"
            ) as mock_logger,
        ):
            with pytest.raises(SSHException):
                connect_ssh("test-driver", "10.0.0.1", "admin", "secret")

        mock_logger.error.assert_called_once()
        assert mock_logger.error.call_args[0][0] == FIPS_CRYPTO_ERROR


class TestFIPSSSHConfigAllowLists:
    def test_ciphers_contain_only_aes_variants(self) -> None:
        for cipher in FIPS_SSH_CONFIG.ciphers:
            assert "aes" in cipher, (
                f"Non-AES cipher in FIPS allow-list: {cipher!r}"
            )

    def test_ciphers_exclude_arcfour(self) -> None:
        assert not any(
            c.startswith("arcfour") for c in FIPS_SSH_CONFIG.ciphers
        )

    def test_ciphers_exclude_blowfish(self) -> None:
        assert not any("blowfish" in c for c in FIPS_SSH_CONFIG.ciphers)

    def test_kex_excludes_sha1_variants(self) -> None:
        for kex in FIPS_SSH_CONFIG.kex:
            assert "sha1" not in kex, f"SHA-1 kex in FIPS allow-list: {kex!r}"

    def test_kex_excludes_diffie_hellman_group1(self) -> None:
        assert "diffie-hellman-group1-sha1" not in FIPS_SSH_CONFIG.kex

    def test_macs_contain_only_hmac_sha2_variants(self) -> None:
        for mac in FIPS_SSH_CONFIG.macs:
            assert "sha2" in mac, f"Non-SHA-2 MAC in FIPS allow-list: {mac!r}"

    def test_macs_exclude_hmac_md5(self) -> None:
        assert "hmac-md5" not in FIPS_SSH_CONFIG.macs
        assert "hmac-md5-96" not in FIPS_SSH_CONFIG.macs

    def test_key_types_exclude_dsa_and_ed25519(self) -> None:
        assert "ssh-dss" not in FIPS_SSH_CONFIG.key_types
        assert "ssh-ed25519" not in FIPS_SSH_CONFIG.key_types

    def test_key_types_include_ecdsa_and_rsa(self) -> None:
        assert any("ecdsa" in kt for kt in FIPS_SSH_CONFIG.key_types), (
            "No ECDSA key type in FIPS allow-list"
        )
        assert any("rsa" in kt for kt in FIPS_SSH_CONFIG.key_types), (
            "No RSA key type in FIPS allow-list"
        )


class TestGenerateSSHKeyFIPSSafe:
    def test_rejects_dsa_in_fips_mode(self) -> None:
        from provisioningserver.testing.security import (
            FIPSCryptoError,
            generate_ssh_key,
        )

        with (
            patch(
                "provisioningserver.testing.security.is_fips_enabled",
                return_value=True,
            ),
            pytest.raises(FIPSCryptoError, match="DSA"),
        ):
            generate_ssh_key("dsa")

    def test_rejects_rsa_below_2048_in_fips_mode(self) -> None:
        from provisioningserver.testing.security import (
            FIPSCryptoError,
            generate_ssh_key,
        )

        with (
            patch(
                "provisioningserver.testing.security.is_fips_enabled",
                return_value=True,
            ),
            pytest.raises(FIPSCryptoError, match="1024"),
        ):
            generate_ssh_key("rsa", bits=1024)

    def test_rejects_ed25519_in_fips_mode(self) -> None:
        from provisioningserver.testing.security import (
            FIPSCryptoError,
            generate_ssh_key,
        )

        with (
            patch(
                "provisioningserver.testing.security.is_fips_enabled",
                return_value=True,
            ),
            pytest.raises(FIPSCryptoError, match="ED25519"),
        ):
            generate_ssh_key("ed25519")

    def test_accepts_rsa_2048_in_fips_mode(self) -> None:
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

        from provisioningserver.testing.security import generate_ssh_key

        with patch(
            "provisioningserver.testing.security.is_fips_enabled", return_value=True
        ):
            key = generate_ssh_key("rsa", bits=2048)

        assert isinstance(key, RSAPrivateKey)
        assert key.key_size == 2048

    def test_accepts_ecdsa_in_fips_mode(self) -> None:
        from cryptography.hazmat.primitives.asymmetric.ec import (
            EllipticCurvePrivateKey,
        )

        from provisioningserver.testing.security import generate_ssh_key

        with patch(
            "provisioningserver.testing.security.is_fips_enabled", return_value=True
        ):
            key = generate_ssh_key("ecdsa")

        assert isinstance(key, EllipticCurvePrivateKey)

    def test_defaults_rsa_to_4096_bits_in_fips_mode(self) -> None:
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

        from provisioningserver.testing.security import generate_ssh_key

        with patch(
            "provisioningserver.testing.security.is_fips_enabled", return_value=True
        ):
            key = generate_ssh_key("rsa")

        assert isinstance(key, RSAPrivateKey)
        assert key.key_size == 4096

    def test_allows_dsa_outside_fips_mode(self) -> None:
        from cryptography.hazmat.primitives.asymmetric.dsa import DSAPrivateKey

        from provisioningserver.testing.security import generate_ssh_key

        with patch(
            "provisioningserver.testing.security.is_fips_enabled", return_value=False
        ):
            key = generate_ssh_key("dsa")

        assert isinstance(key, DSAPrivateKey)

    def test_allows_rsa_below_2048_outside_fips_mode(self) -> None:
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

        from provisioningserver.testing.security import generate_ssh_key

        with patch(
            "provisioningserver.testing.security.is_fips_enabled", return_value=False
        ):
            key = generate_ssh_key("rsa", bits=1024)

        assert isinstance(key, RSAPrivateKey)
        assert key.key_size == 1024

    def test_allows_ed25519_outside_fips_mode(self) -> None:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

        from provisioningserver.testing.security import generate_ssh_key

        with patch(
            "provisioningserver.testing.security.is_fips_enabled", return_value=False
        ):
            key = generate_ssh_key("ed25519")

        assert isinstance(key, Ed25519PrivateKey)

    def test_raises_for_unknown_key_type(self) -> None:
        from provisioningserver.testing.security import generate_ssh_key

        with (
            patch(
                "provisioningserver.testing.security.is_fips_enabled",
                return_value=False,
            ),
            pytest.raises(ValueError, match="Unsupported SSH key type"),
        ):
            generate_ssh_key("xmss")
