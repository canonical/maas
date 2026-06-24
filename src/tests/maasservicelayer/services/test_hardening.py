#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Tests for HardeningValidator (maasservicelayer.services.hardening)."""

import datetime
import logging
import os
from pathlib import Path
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pytest

from maascommon.hardening import HardeningConfig, HardeningMode
from maasservicelayer.services.hardening import HardeningValidator


def _active_config() -> HardeningConfig:
    """Return a HardeningConfig with hardening_active == True."""
    return HardeningConfig(mode=HardeningMode.AUTO, fips_enabled=True)


def _inactive_config() -> HardeningConfig:
    """Return a HardeningConfig with hardening_active == False."""
    return HardeningConfig(mode=HardeningMode.AUTO, fips_enabled=False)


def _generate_private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _generate_cert(private_key: rsa.RSAPrivateKey) -> x509.Certificate:
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "maas-test")])
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(private_key, hashes.SHA256())
    )


def _write_cert(path: Path, cert: x509.Certificate) -> None:
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _write_key(path: Path, key: rsa.RSAPrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )


class TestHardeningValidatorInactive:
    def test_returns_valid_immediately_no_file_ops(
        self, tmp_path: Path
    ) -> None:
        """When hardening is not active validate() returns valid with no I/O."""
        config = _inactive_config()
        nonexistent = str(tmp_path / "nowhere.pem")
        validator = HardeningValidator(
            config=config,
            api_tls_cert=nonexistent,
            api_tls_key=nonexistent,
            api_tls_dhparam=nonexistent,
        )

        # Patch os.stat so any accidental I/O is detected.
        with patch("os.stat", side_effect=AssertionError("unexpected I/O")):
            result = validator.validate()

        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []


class TestValidateTLSCert:
    def test_missing_cert_returns_missing_tls_cert(
        self, tmp_path: Path
    ) -> None:
        config = _active_config()
        cert_path = str(tmp_path / "cert.pem")  # does not exist
        key_path = str(tmp_path / "key.pem")

        validator = HardeningValidator(
            config=config,
            api_tls_cert=cert_path,
            api_tls_key=key_path,
        )
        errors = validator._validate_tls_cert()

        assert len(errors) == 1
        assert errors[0].code == "MISSING_TLS_CERT"
        assert errors[0].config_key == "api_tls_cert"
        assert errors[0].file_path == cert_path

    def test_missing_key_returns_missing_tls_key(self, tmp_path: Path) -> None:
        config = _active_config()
        key = _generate_private_key()
        cert = _generate_cert(key)

        cert_path = tmp_path / "cert.pem"
        _write_cert(cert_path, cert)

        key_path = str(tmp_path / "key.pem")  # does not exist

        validator = HardeningValidator(
            config=config,
            api_tls_cert=str(cert_path),
            api_tls_key=key_path,
        )
        errors = validator._validate_tls_cert()

        assert len(errors) == 1
        assert errors[0].code == "MISSING_TLS_KEY"
        assert errors[0].config_key == "api_tls_key"
        assert errors[0].file_path == key_path

    def test_cert_present_key_none_returns_missing_tls_key(
        self, tmp_path: Path
    ) -> None:
        """Cert file exists but api_tls_key is None → MISSING_TLS_KEY."""
        config = _active_config()
        key = _generate_private_key()
        cert = _generate_cert(key)
        cert_path = tmp_path / "cert.pem"
        _write_cert(cert_path, cert)

        validator = HardeningValidator(
            config=config,
            api_tls_cert=str(cert_path),
            api_tls_key=None,
        )
        errors = validator._validate_tls_cert()

        assert len(errors) == 1
        assert errors[0].code == "MISSING_TLS_KEY"
        assert errors[0].config_key == "api_tls_key"

    def test_cert_key_mismatch_returns_error(self, tmp_path: Path) -> None:
        config = _active_config()
        key1 = _generate_private_key()
        key2 = _generate_private_key()
        cert = _generate_cert(key1)  # signed with key1

        cert_path = tmp_path / "cert.pem"
        _write_cert(cert_path, cert)

        key_path = tmp_path / "key.pem"
        _write_key(key_path, key2)  # different key

        validator = HardeningValidator(
            config=config,
            api_tls_cert=str(cert_path),
            api_tls_key=str(key_path),
        )
        errors = validator._validate_tls_cert()

        assert len(errors) == 1
        assert errors[0].code == "TLS_CERT_KEY_MISMATCH"
        assert errors[0].config_key == "api_tls_cert"

    def test_valid_matching_pair_returns_no_errors(
        self, tmp_path: Path
    ) -> None:
        config = _active_config()
        key = _generate_private_key()
        cert = _generate_cert(key)

        cert_path = tmp_path / "cert.pem"
        _write_cert(cert_path, cert)

        key_path = tmp_path / "key.pem"
        _write_key(key_path, key)

        validator = HardeningValidator(
            config=config,
            api_tls_cert=str(cert_path),
            api_tls_key=str(key_path),
        )
        errors = validator._validate_tls_cert()

        assert errors == []


class TestValidateDHParams:
    def test_no_dhparam_returns_no_errors(self) -> None:
        config = _active_config()
        validator = HardeningValidator(config=config, api_tls_dhparam=None)
        assert validator._validate_dh_params() == []

    def test_missing_file_returns_no_errors(self, tmp_path: Path) -> None:
        config = _active_config()
        validator = HardeningValidator(
            config=config,
            api_tls_dhparam=str(tmp_path / "dhparam.pem"),
        )
        assert validator._validate_dh_params() == []

    def test_corrupt_file_returns_parse_error_code(
        self, tmp_path: Path
    ) -> None:
        config = _active_config()
        dhparam_path = tmp_path / "dhparam.pem"
        dhparam_path.write_text("not a valid PEM file")

        validator = HardeningValidator(
            config=config,
            api_tls_dhparam=str(dhparam_path),
        )
        errors = validator._validate_dh_params()

        assert len(errors) == 1
        assert errors[0].code == "DH_PARAMS_PARSE_ERROR"
        assert errors[0].config_key == "api_tls_dhparam"
        assert errors[0].file_path == str(dhparam_path)


class TestValidateKeyPermissions:
    def test_insecure_perms_0644_returns_error(self, tmp_path: Path) -> None:
        config = _active_config()
        key_path = tmp_path / "key.pem"
        key_path.write_text("dummy key data")
        os.chmod(key_path, 0o644)

        validator = HardeningValidator(
            config=config,
            api_tls_key=str(key_path),
        )
        errors = validator._validate_key_permissions()

        assert len(errors) == 1
        assert errors[0].code == "INSECURE_KEY_PERMISSIONS"
        assert errors[0].config_key == "api_tls_key"
        assert errors[0].file_path == str(key_path)

    def test_secure_perms_0600_returns_no_error(self, tmp_path: Path) -> None:
        config = _active_config()
        key_path = tmp_path / "key.pem"
        key_path.write_text("dummy key data")
        os.chmod(key_path, 0o600)

        validator = HardeningValidator(
            config=config,
            api_tls_key=str(key_path),
        )
        errors = validator._validate_key_permissions()

        assert errors == []


class TestValidateBindings:
    def test_no_api_bind_returns_no_errors(self) -> None:
        config = _active_config()
        validator = HardeningValidator(config=config, api_bind=None)
        assert validator._validate_bindings() == []

    def test_empty_api_bind_returns_no_errors(self) -> None:
        config = _active_config()
        validator = HardeningValidator(config=config, api_bind="")
        assert validator._validate_bindings() == []

    def test_valid_ipv4_returns_no_errors(self) -> None:
        config = _active_config()
        validator = HardeningValidator(config=config, api_bind="0.0.0.0")
        assert validator._validate_bindings() == []

    def test_valid_ipv4_specific_returns_no_errors(self) -> None:
        config = _active_config()
        validator = HardeningValidator(config=config, api_bind="192.168.1.1")
        assert validator._validate_bindings() == []

    def test_valid_ipv6_returns_no_errors(self) -> None:
        config = _active_config()
        validator = HardeningValidator(config=config, api_bind="::")
        assert validator._validate_bindings() == []

    def test_hostname_returns_invalid_bind_address_error(self) -> None:
        config = _active_config()
        validator = HardeningValidator(config=config, api_bind="not-an-ip")
        errors = validator._validate_bindings()
        assert len(errors) == 1
        assert errors[0].code == "INVALID_BIND_ADDRESS"
        assert errors[0].config_key == "api_bind"
        assert "not-an-ip" in errors[0].message

    def test_invalid_bind_propagates_into_validate(self) -> None:
        config = _active_config()
        validator = HardeningValidator(config=config, api_bind="bad-address")
        result = validator.validate()
        assert result.is_valid is False
        assert any(e.code == "INVALID_BIND_ADDRESS" for e in result.errors)


class TestHardeningValidatorFullValidate:
    def test_validate_active_no_paths_returns_valid(self) -> None:
        """All paths None → skip all checks → valid result."""
        config = _active_config()
        validator = HardeningValidator(config=config)
        result = validator.validate()
        assert result.is_valid is True
        assert result.errors == []

    def test_validate_active_with_errors_returns_invalid(
        self, tmp_path: Path
    ) -> None:
        """A missing cert file propagates into the aggregate result."""
        config = _active_config()
        validator = HardeningValidator(
            config=config,
            api_tls_cert=str(tmp_path / "missing.pem"),
            api_tls_key=str(tmp_path / "missing-key.pem"),
        )
        result = validator.validate()
        assert result.is_valid is False
        assert any(e.code == "MISSING_TLS_CERT" for e in result.errors)


class TestRunHardeningStartupValidation:
    """Cover the startup-integration helper: no-op when inactive, exit on
    invalid, log on failure. Uses ``get_hardening_config.cache_clear()`` to
    flip between FIPS-on/FIPS-off across tests.
    """

    def setup_method(self) -> None:
        from maascommon.hardening import get_hardening_config

        get_hardening_config.cache_clear()

    def test_inactive_returns_valid_without_io(self, tmp_path: Path) -> None:
        """When hardening is inactive the helper is a no-op (no I/O)."""
        from maascommon.hardening import get_hardening_config
        from maasservicelayer.services.hardening import (
            run_hardening_startup_validation,
        )

        get_hardening_config.cache_clear()
        with patch("maascommon.hardening.is_fips_enabled", return_value=False):
            with patch(
                "os.stat", side_effect=AssertionError("unexpected I/O")
            ):
                result = run_hardening_startup_validation(
                    api_tls_cert=str(tmp_path / "missing.pem"),
                    api_tls_key=str(tmp_path / "missing-key.pem"),
                )

        assert result.is_valid is True
        assert result.errors == []

    def test_active_with_missing_cert_exits(self, tmp_path: Path) -> None:
        """Active hardening + missing cert → SystemExit(1)."""
        from maascommon.hardening import get_hardening_config
        from maasservicelayer.services.hardening import (
            run_hardening_startup_validation,
        )

        get_hardening_config.cache_clear()
        with patch("maascommon.hardening.is_fips_enabled", return_value=True):
            with pytest.raises(SystemExit) as exc_info:
                run_hardening_startup_validation(
                    api_tls_cert=str(tmp_path / "missing.pem"),
                )

        assert exc_info.value.code == 1

    def test_active_with_valid_paths_returns_valid(
        self, tmp_path: Path
    ) -> None:
        """Active hardening + valid matching cert/key → valid result."""
        from maascommon.hardening import get_hardening_config
        from maasservicelayer.services.hardening import (
            run_hardening_startup_validation,
        )

        key = _generate_private_key()
        cert = _generate_cert(key)
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"
        _write_cert(cert_path, cert)
        _write_key(key_path, key)
        os.chmod(key_path, 0o600)

        get_hardening_config.cache_clear()
        with patch("maascommon.hardening.is_fips_enabled", return_value=True):
            result = run_hardening_startup_validation(
                api_tls_cert=str(cert_path),
                api_tls_key=str(key_path),
            )

        assert result.is_valid is True
        assert result.errors == []

    def test_active_with_errors_logs_each_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Each HardeningError is logged via the ``maas.hardening`` logger."""
        from maascommon.hardening import get_hardening_config
        from maasservicelayer.services.hardening import (
            run_hardening_startup_validation,
        )

        get_hardening_config.cache_clear()
        with patch("maascommon.hardening.is_fips_enabled", return_value=True):
            with caplog.at_level(logging.ERROR, logger="maas.hardening"):
                with pytest.raises(SystemExit):
                    run_hardening_startup_validation(
                        api_tls_cert=str(tmp_path / "missing.pem"),
                    )

        assert any("MISSING_TLS_CERT" in rec.message for rec in caplog.records)
