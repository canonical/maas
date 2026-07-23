#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Unit tests for maascommon.fips — FIPS detection and SSH allow-lists."""

import logging

import pytest

from maascommon.fips import (
    FIPS_SSH_CONFIG,
    get_fips_status,
    validate_fips_ssh_public_key,
)


@pytest.fixture(autouse=True)
def clear_fips_cache():
    """Clear lru_cache before and after each test for isolation."""
    get_fips_status.cache_clear()
    yield
    get_fips_status.cache_clear()


class TestGetFipsStatus:
    def test_file_missing_returns_not_enabled(self, tmp_path, monkeypatch):
        missing = tmp_path / "fips_enabled"
        monkeypatch.setattr("maascommon.fips.FIPS_PROC_PATH", missing)
        status = get_fips_status()
        assert status.enabled is False
        assert status.detection_error is None

    def test_file_zero_returns_not_enabled(self, tmp_path, monkeypatch):
        fips_file = tmp_path / "fips_enabled"
        fips_file.write_text("0\n")
        monkeypatch.setattr("maascommon.fips.FIPS_PROC_PATH", fips_file)
        status = get_fips_status()
        assert status.enabled is False
        assert status.detection_error is None

    def test_file_one_returns_enabled(self, tmp_path, monkeypatch):
        fips_file = tmp_path / "fips_enabled"
        fips_file.write_text("1\n")
        monkeypatch.setattr("maascommon.fips.FIPS_PROC_PATH", fips_file)
        status = get_fips_status()
        assert status.enabled is True
        assert status.detection_error is None

    def test_oserror_returns_not_enabled_with_error(
        self, tmp_path, monkeypatch
    ):
        fips_file = tmp_path / "fips_enabled"
        fips_file.write_text("1")
        monkeypatch.setattr("maascommon.fips.FIPS_PROC_PATH", fips_file)

        def raise_oserror(self_path, *args, **kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr("pathlib.Path.read_text", raise_oserror)
        status = get_fips_status()
        assert status.enabled is False
        assert status.detection_error is not None
        assert "permission denied" in status.detection_error

    def test_result_is_cached(self, tmp_path, monkeypatch):
        fips_file = tmp_path / "fips_enabled"
        fips_file.write_text("1")
        monkeypatch.setattr("maascommon.fips.FIPS_PROC_PATH", fips_file)
        first = get_fips_status()
        second = get_fips_status()
        assert first is second

    def test_logs_info_on_detection(self, tmp_path, monkeypatch, caplog):
        fips_file = tmp_path / "fips_enabled"
        fips_file.write_text("1")
        monkeypatch.setattr("maascommon.fips.FIPS_PROC_PATH", fips_file)
        with caplog.at_level(logging.INFO, logger="maas.fips"):
            get_fips_status()
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.INFO

    def test_logs_warning_on_oserror(self, tmp_path, monkeypatch, caplog):
        fips_file = tmp_path / "fips_enabled"
        fips_file.write_text("1")
        monkeypatch.setattr("maascommon.fips.FIPS_PROC_PATH", fips_file)

        def raise_oserror(self_path, *args, **kwargs):
            raise OSError("no permission")

        monkeypatch.setattr("pathlib.Path.read_text", raise_oserror)
        with caplog.at_level(logging.WARNING, logger="maas.fips"):
            get_fips_status()
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.WARNING


class TestFIPSSSHConfig:
    def test_ciphers_are_aes_modes(self):
        expected = frozenset(
            {
                "aes128-ctr",
                "aes192-ctr",
                "aes256-ctr",
                "aes128-gcm@openssh.com",
                "aes256-gcm@openssh.com",
            }
        )
        assert frozenset(FIPS_SSH_CONFIG.ciphers) == expected

    def test_kex_are_ecdh_or_dh_sha256(self):
        expected = frozenset(
            {
                "ecdh-sha2-nistp256",
                "ecdh-sha2-nistp384",
                "diffie-hellman-group14-sha256",
            }
        )
        assert frozenset(FIPS_SSH_CONFIG.kex) == expected

    def test_macs_are_hmac_sha2(self):
        assert frozenset(FIPS_SSH_CONFIG.macs) == frozenset(
            {"hmac-sha2-256", "hmac-sha2-512"}
        )

    def test_key_types_are_ecdsa_and_rsa_sha2(self):
        # Wire-level key types: ECDSA and RSA with SHA-2 signatures only.
        # No DSA (ssh-dss) and no Ed25519 (not in OpenSSL 3.0 FIPS provider).
        assert frozenset(FIPS_SSH_CONFIG.key_types) == frozenset(
            {"ecdsa-sha2-nistp256", "rsa-sha2-256", "rsa-sha2-512"}
        )

    def test_is_immutable(self):
        with pytest.raises(AttributeError):
            FIPS_SSH_CONFIG.ciphers = ("bad",)  # type: ignore[misc]


# A real 2048-bit RSA public key (body only) used to exercise the SSH wire
# parser in rsa_ssh_key_bits / validate_fips_ssh_public_key.
_RSA2048_BODY = (
    "AAAAB3NzaC1yc2EAAAADAQABAAABAQDdrzzDZNwyMVBvBTT6kBnrfPZv/AUbk"
    "xj7G5CaMTdw6xkKthV22EntD3lxaQxRKzQTfCc2d/CC1K4ushCcRs1S6SQ2zJ2jDq1UmO"
    "UkDMgvNh4JVhJYSKc6mu8i3s7oGSmBado5wvtlpSzMrscOpf8Qe/wmT5fH12KB9ipJqoF"
    "NQMVbVcVarE/v6wpn3GZC62YRb5iaz9/M+t92Qhu50W2u+KfouqtKB2lwIDDKZMww38Ex"
    "tdMouh2FZpxaoh4Uey5bRp3tM3JgnWcX6fyUOp2gxJRPIlD9rrZhX5IkEkZM8MQbdPTQL"
    "gIf98oFph5RG6w1t02BvI9nJKM7KkKEfBHt"
)


class TestValidateFipsSshPublicKey:
    def test_rejects_dsa(self):
        msg = validate_fips_ssh_public_key("ssh-dss AAAA comment")
        assert msg is not None and "ssh-dss" in msg

    def test_rejects_ed25519(self):
        msg = validate_fips_ssh_public_key("ssh-ed25519 AAAA comment")
        assert msg is not None and "ssh-ed25519" in msg

    def test_accepts_ecdsa(self):
        assert (
            validate_fips_ssh_public_key("ecdsa-sha2-nistp256 AAAA c") is None
        )

    def test_accepts_rsa_2048(self):
        assert (
            validate_fips_ssh_public_key(f"ssh-rsa {_RSA2048_BODY} c") is None
        )

    def test_rejects_small_rsa(self, monkeypatch):
        monkeypatch.setattr(
            "maascommon.fips.rsa_ssh_key_bits", lambda _b64: 1024
        )
        msg = validate_fips_ssh_public_key("ssh-rsa AAAA c")
        assert msg is not None and "1024" in msg

    def test_empty_key_returns_none(self):
        assert validate_fips_ssh_public_key("") is None
