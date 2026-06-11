#  Copyright 2026 Canonical Ltd.  This software is licensed under the GNU Affero General Public License version 3 (see the file LICENSE).

import base64
import struct
from unittest.mock import mock_open, patch

import maascommon.fips as fips_module
from maascommon.fips import (
    _parse_rsa_key_bits,
    validate_ssh_key_fips_compliance,
)


class TestFIPS:
    @patch("builtins.open", new_callable=mock_open, read_data="1\n")
    def test_detect_fips_mode_enabled(self, _mock_open):
        assert fips_module.detect_fips_mode() is True

    @patch("builtins.open", new_callable=mock_open, read_data="0\n")
    def test_detect_fips_mode_disabled(self, _mock_open):
        assert fips_module.detect_fips_mode() is False

    @patch("builtins.open", side_effect=OSError)
    def test_detect_fips_mode_missing_file(self, _mock_open):
        assert fips_module.detect_fips_mode() is False

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_detect_fips_mode_file_not_found_no_warning(self, _mock_open):
        with patch.object(fips_module.logger, "warning") as mock_warning:
            assert fips_module.detect_fips_mode() is False
        mock_warning.assert_not_called()

    @patch("builtins.open", side_effect=PermissionError("Access denied"))
    def test_detect_fips_mode_oserror_logs_warning(self, _mock_open):
        with patch.object(fips_module.logger, "warning") as mock_warning:
            assert fips_module.detect_fips_mode() is False
        mock_warning.assert_called_once()

    def test_is_fips_enabled_returns_cached(self):
        with (
            patch.object(fips_module, "_fips_checked", True),
            patch.object(fips_module, "_fips_value", True),
        ):
            assert fips_module.is_fips_enabled() is True

    def test_fips_status_model(self):
        status = fips_module.FIPSStatus(
            fips_enabled=True,
            detection_source="/proc/sys/crypto/fips_enabled",
        )

        assert status.fips_enabled is True
        assert status.detection_source == "/proc/sys/crypto/fips_enabled"

    def test_get_fips_ssh_config_returns_allow_lists(self):
        result = fips_module.get_fips_ssh_config()

        # The function returns explicit allow-lists, not disabled sets.
        assert "hmac-md5" not in result["macs"]
        assert "3des-cbc" not in result["ciphers"]
        assert "hmac-sha2-256" in result["macs"]
        assert "aes128-ctr" in result["ciphers"]

    def test_fips_ssh_config_singleton(self):
        assert isinstance(
            fips_module.FIPS_SSH_CONFIG,
            fips_module.FIPSSSHConfig,
        )
        assert fips_module.FIPS_SSH_CONFIG.ciphers == (
            "aes128-ctr",
            "aes192-ctr",
            "aes256-ctr",
            "aes128-gcm@openssh.com",
            "aes256-gcm@openssh.com",
        )


def _make_rsa_blob(key_size_bytes: int) -> str:
    """Build a minimal synthetic SSH RSA public key blob with the given modulus size."""

    def encode_mpint(data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + data

    algo = b"ssh-rsa"
    exponent = b"\x01\x00\x01"  # 65537
    modulus = (
        b"\x00" + b"\xff" * key_size_bytes
    )  # leading 0x00 to keep positive
    blob = (
        struct.pack(">I", len(algo))
        + algo
        + encode_mpint(exponent)
        + encode_mpint(modulus)
    )
    return base64.b64encode(blob).decode()


class TestParseRsaKeyBits:
    def test_1024_bit_key(self):
        blob = _make_rsa_blob(128)  # 128 bytes = 1024-bit modulus field
        bits = _parse_rsa_key_bits(blob)
        # The leading 0x00 byte is stripped during bit_length, result is 1016 or 1024
        # depending on the ff bytes; what matters is it is well below 2048.
        assert bits is not None
        assert bits < 2048

    def test_4096_bit_key(self):
        blob = _make_rsa_blob(512)  # 512 bytes = 4096-bit modulus field
        bits = _parse_rsa_key_bits(blob)
        assert bits is not None
        assert bits >= 2048

    def test_returns_none_on_invalid_blob(self):
        assert _parse_rsa_key_bits("not-valid-base64!!!") is None

    def test_returns_none_on_truncated_blob(self):
        assert (
            _parse_rsa_key_bits(base64.b64encode(b"\x00\x00\x00\x07").decode())
            is None
        )


class TestValidateSshKeyFipsComplianceRsaSize:
    def test_rejects_small_rsa_key_via_rsa_sha2_256_type(self):
        # Construct a synthetic rsa-sha2-256 key line with a 1024-bit modulus.
        blob = _make_rsa_blob(128)
        key_str = f"rsa-sha2-256 {blob} comment"
        valid, reason, _ = validate_ssh_key_fips_compliance(key_str)
        assert not valid
        assert reason is not None
        assert "2048" in reason

    def test_accepts_large_rsa_key_via_rsa_sha2_256_type(self):
        blob = _make_rsa_blob(256)  # 256 bytes -> >= 2048 bits
        key_str = f"rsa-sha2-256 {blob} comment"
        valid, reason, _ = validate_ssh_key_fips_compliance(key_str)
        assert valid
        assert reason is None

    def test_ssh_rsa_small_key_rejected_for_algorithm(self):
        # ssh-rsa is rejected for algorithm reasons before reaching the size check.
        blob = _make_rsa_blob(128)
        key_str = f"ssh-rsa {blob} comment"
        valid, reason, _ = validate_ssh_key_fips_compliance(key_str)
        assert not valid
        # Rejected because ssh-rsa is not in FIPS_ALLOWED_SSH_KEY_TYPES
        assert reason is not None
