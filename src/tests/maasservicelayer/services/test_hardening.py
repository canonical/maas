#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Tests for HardeningValidator (maasservicelayer.services.hardening).

validate() returns list[HardeningViolation] — never exits or raises.
"""

import datetime
import logging
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pytest

from maasservicelayer.services.hardening import (
    _ident,
    configure_and_validate_hardening,
    HardeningValidator,
)


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


def _cert_pem(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


def _key_pem(key: rsa.RSAPrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )


class TestIdentHelper:
    def test_lower_hyphenated(self) -> None:
        # _ident transforms UPPER_SNAKE → lower-hyphen, prefixed with
        # "hardening-", and truncates the slug to 29 chars.
        result = _ident("MISSING_TLS_CERT")
        assert result.startswith("hardening-")
        slug = result[len("hardening-") :]
        assert slug == slug.lower()
        assert "_" not in slug
        assert len(slug) <= 29


class TestHardeningValidatorInactive:
    def test_returns_empty_list_when_inactive(self) -> None:
        validator = HardeningValidator(hardening_active=False)
        assert validator.validate() == []


class TestValidateTLSCert:
    def test_no_cert_pem_returns_missing_tls_cert(self) -> None:
        validator = HardeningValidator(
            hardening_active=True,
            api_tls_cert_pem=None,
            api_tls_key_pem=None,
        )
        violations = validator._validate_tls_cert()
        assert len(violations) == 1
        assert violations[0].code == "MISSING_TLS_CERT"
        assert violations[0].config_key == "tls"
        assert "config-tls" in violations[0].resolution

    def test_cert_present_key_missing_returns_missing_tls_key(self) -> None:
        key = _generate_private_key()
        cert = _generate_cert(key)
        validator = HardeningValidator(
            hardening_active=True,
            api_tls_cert_pem=_cert_pem(cert),
            api_tls_key_pem=None,
        )
        violations = validator._validate_tls_cert()
        assert len(violations) == 1
        assert violations[0].code == "MISSING_TLS_KEY"

    def test_matching_cert_and_key_returns_no_violations(self) -> None:
        key = _generate_private_key()
        cert = _generate_cert(key)
        validator = HardeningValidator(
            hardening_active=True,
            api_tls_cert_pem=_cert_pem(cert),
            api_tls_key_pem=_key_pem(key),
        )
        assert validator._validate_tls_cert() == []

    def test_mismatched_cert_and_key_returns_violation(self) -> None:
        key1 = _generate_private_key()
        key2 = _generate_private_key()
        cert = _generate_cert(key1)
        validator = HardeningValidator(
            hardening_active=True,
            api_tls_cert_pem=_cert_pem(cert),
            api_tls_key_pem=_key_pem(key2),
        )
        violations = validator._validate_tls_cert()
        assert len(violations) == 1
        assert violations[0].code == "TLS_CERT_KEY_MISMATCH"

    def test_corrupt_pem_returns_parse_error(self) -> None:
        validator = HardeningValidator(
            hardening_active=True,
            api_tls_cert_pem=b"not-a-cert",
            api_tls_key_pem=b"not-a-key",
        )
        violations = validator._validate_tls_cert()
        assert len(violations) == 1
        assert violations[0].code == "TLS_CERT_PARSE_ERROR"


class TestValidateDHParams:
    def test_no_dhparam_returns_no_violations(self) -> None:
        validator = HardeningValidator(
            hardening_active=True, api_tls_dhparam=None
        )
        assert validator._validate_dh_params() == []

    def test_nonexistent_dhparam_file_returns_no_violations(
        self, tmp_path: Path
    ) -> None:
        validator = HardeningValidator(
            hardening_active=True,
            api_tls_dhparam=str(tmp_path / "dhparam.pem"),
        )
        assert validator._validate_dh_params() == []

    def test_weak_dh_params_returns_violation(self, tmp_path: Path) -> None:
        from cryptography.hazmat.primitives.asymmetric.dh import (
            generate_parameters,
        )

        params = generate_parameters(generator=2, key_size=512)
        dhparam_path = tmp_path / "dhparam.pem"
        dhparam_path.write_bytes(
            params.parameter_bytes(
                serialization.Encoding.PEM,
                serialization.ParameterFormat.PKCS3,
            )
        )
        validator = HardeningValidator(
            hardening_active=True,
            api_tls_dhparam=str(dhparam_path),
        )
        violations = validator._validate_dh_params()
        assert len(violations) == 1
        assert violations[0].code == "WEAK_DH_PARAMS"
        assert violations[0].file_path == str(dhparam_path)

    def test_strong_dh_params_returns_no_violations(
        self, tmp_path: Path
    ) -> None:
        from cryptography.hazmat.primitives.asymmetric.dh import (
            generate_parameters,
        )

        params = generate_parameters(generator=2, key_size=2048)
        dhparam_path = tmp_path / "dhparam.pem"
        dhparam_path.write_bytes(
            params.parameter_bytes(
                serialization.Encoding.PEM,
                serialization.ParameterFormat.PKCS3,
            )
        )
        validator = HardeningValidator(
            hardening_active=True,
            api_tls_dhparam=str(dhparam_path),
        )
        assert validator._validate_dh_params() == []


class TestValidateBindings:
    """Per-key wildcard/empty binding violations."""

    _ALL_SPECIFIC = {
        "api_bind": "10.0.0.1",
        "api_bind6": "fd00::1",
        "prometheus_bind": "127.0.0.1",
        "temporal_bind": "127.0.0.1",
        "rpc_bind": "10.0.0.2",
        "dns_bind": "10.0.0.3",
    }

    def _validator(self, **overrides) -> HardeningValidator:
        kwargs = {**self._ALL_SPECIFIC, **overrides}
        return HardeningValidator(hardening_active=True, **kwargs)

    def test_all_specific_addresses_no_violations(self) -> None:
        assert self._validator()._validate_bindings() == []

    def test_each_key_unset_produces_its_own_violation(self) -> None:
        for key in self._ALL_SPECIFIC:
            v_list = self._validator(**{key: None})._validate_bindings()
            assert len(v_list) == 1, f"expected 1 violation for {key}"
            assert v_list[0].code == "WILDCARD_BIND_NOT_ALLOWED"
            assert v_list[0].config_key == key
            assert (
                v_list[0].ident
                == f"hardening-wildcard-bind-{key.replace('_', '-')}"
            )

    def test_each_key_ipv4_wildcard_produces_its_own_violation(self) -> None:
        for key in ("api_bind", "prometheus_bind", "rpc_bind"):
            v_list = self._validator(**{key: "0.0.0.0"})._validate_bindings()
            assert any(
                v.code == "WILDCARD_BIND_NOT_ALLOWED" and v.config_key == key
                for v in v_list
            ), f"expected WILDCARD violation for {key}"

    def test_each_key_ipv6_wildcard_produces_its_own_violation(self) -> None:
        v_list = self._validator(api_bind6="::")._validate_bindings()
        assert any(
            v.code == "WILDCARD_BIND_NOT_ALLOWED"
            and v.config_key == "api_bind6"
            for v in v_list
        )

    def test_invalid_ip_returns_invalid_bind_violation(self) -> None:
        v_list = self._validator(api_bind="not-an-ip")._validate_bindings()
        assert len(v_list) == 1
        assert v_list[0].code == "INVALID_BIND_ADDRESS"
        assert v_list[0].config_key == "api_bind"
        assert "not-an-ip" in v_list[0].message

    def test_multiple_offending_keys_produce_independent_violations(
        self,
    ) -> None:
        v_list = self._validator(
            prometheus_bind=None, temporal_bind=None
        )._validate_bindings()
        codes = [v.config_key for v in v_list]
        assert "prometheus_bind" in codes
        assert "temporal_bind" in codes
        # Other keys are specific — no other violations.
        assert len(v_list) == 2


class TestValidateFipsDrift:
    """FIPS config/status drift detection."""

    def test_unset_returns_no_violations(self) -> None:
        v = HardeningValidator(
            hardening_active=False,
            fips_declared=None,
            fips_active=True,
        )
        assert v._validate_fips_drift() == []

    def test_declared_on_host_on_no_violation(self) -> None:
        v = HardeningValidator(
            hardening_active=False,
            fips_declared=True,
            fips_active=True,
        )
        assert v._validate_fips_drift() == []

    def test_declared_off_host_off_no_violation(self) -> None:
        v = HardeningValidator(
            hardening_active=False,
            fips_declared=False,
            fips_active=False,
        )
        assert v._validate_fips_drift() == []

    def test_declared_on_host_off_returns_violation(self) -> None:
        v = HardeningValidator(
            hardening_active=False,
            fips_declared=True,
            fips_active=False,
        )
        violations = v._validate_fips_drift()
        assert len(violations) == 1
        assert violations[0].code == "FIPS_CONFIG_STATUS_MISMATCH"
        assert violations[0].ident == "hardening-fips-config-mismatch"
        assert "declared enabled" in violations[0].message
        assert "set fips_enabled false" in violations[0].resolution

    def test_declared_off_host_on_returns_no_violation(self) -> None:
        v = HardeningValidator(
            hardening_active=False,
            fips_declared=False,
            fips_active=True,
        )
        assert v._validate_fips_drift() == []

    def test_drift_emitted_when_hardening_inactive(self) -> None:
        v = HardeningValidator(
            hardening_active=False,
            fips_declared=True,
            fips_active=False,
        )
        violations = v.validate()
        assert any(v.code == "FIPS_CONFIG_STATUS_MISMATCH" for v in violations)


class TestValidateDbSslmode:
    @pytest.mark.parametrize("mode", ["disable", "allow", "prefer"])
    def test_insecure_sslmode_returns_violation(self, mode: str) -> None:
        validator = HardeningValidator(
            hardening_active=True, database_sslmode=mode
        )
        violations = validator._validate_db_sslmode()
        assert len(violations) == 1
        assert violations[0].code == "INSECURE_DB_SSLMODE"
        assert violations[0].ident == _ident("INSECURE_DB_SSLMODE")

    @pytest.mark.parametrize("mode", ["verify-full", "verify-ca"])
    def test_secure_sslmode_returns_no_violations(self, mode: str) -> None:
        validator = HardeningValidator(
            hardening_active=True, database_sslmode=mode
        )
        assert validator._validate_db_sslmode() == []

    def test_no_sslmode_returns_no_violations(self) -> None:
        validator = HardeningValidator(
            hardening_active=True, database_sslmode=None
        )
        assert validator._validate_db_sslmode() == []


class TestHardeningValidatorFullValidate:
    def test_validate_inactive_returns_empty_list(self) -> None:
        validator = HardeningValidator(
            hardening_active=False, api_bind="0.0.0.0"
        )
        assert validator.validate() == []

    def test_validate_active_specific_bind_no_tls_returns_missing_cert(
        self,
    ) -> None:
        validator = HardeningValidator(
            hardening_active=True, api_bind="10.0.0.5"
        )
        violations = validator.validate()
        assert any(v.code == "MISSING_TLS_CERT" for v in violations)

    def test_validate_never_exits_on_corrupt_pem(self) -> None:
        validator = HardeningValidator(
            hardening_active=True,
            api_tls_cert_pem=b"garbage",
            api_tls_key_pem=b"garbage",
        )
        violations = validator.validate()
        assert any(v.code == "TLS_CERT_PARSE_ERROR" for v in violations)

    def test_insecure_sslmode_included_in_full_validate(self) -> None:
        key = _generate_private_key()
        cert = _generate_cert(key)
        validator = HardeningValidator(
            hardening_active=True,
            api_tls_cert_pem=_cert_pem(cert),
            api_tls_key_pem=_key_pem(key),
            api_bind="10.0.0.1",
            database_sslmode="disable",
        )
        violations = validator.validate()
        assert any(v.code == "INSECURE_DB_SSLMODE" for v in violations)

    def test_violations_are_logged_at_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        validator = HardeningValidator(hardening_active=True)
        with caplog.at_level(logging.ERROR, logger="maas.hardening"):
            validator.validate()
        assert any("MISSING_TLS_CERT" in r.message for r in caplog.records)


class TestConfigureAndValidateHardening:
    @pytest.fixture(autouse=True)
    def _patch_fips(self, mocker):
        mocker.patch(
            "maasservicelayer.services.hardening.is_fips_enabled",
            return_value=False,
        )

    def test_inactive_returns_empty_list(self, mocker) -> None:
        mocker.patch(
            "maasservicelayer.services.hardening.is_hardening_enabled",
            return_value=False,
        )
        result = configure_and_validate_hardening(fips_declared=None)
        assert result == []

    def test_active_no_tls_cert_returns_violations(self, mocker) -> None:
        mocker.patch(
            "maasservicelayer.services.hardening.is_hardening_enabled",
            return_value=True,
        )
        result = configure_and_validate_hardening(
            api_bind="10.0.0.1",
            api_bind6="fd00::1",
            prometheus_bind="127.0.0.1",
            temporal_bind="127.0.0.1",
            rpc_bind="10.0.0.2",
            fips_declared=None,
        )
        assert any(v.code == "MISSING_TLS_CERT" for v in result)

    def test_no_tls_cert_passed_returns_missing_cert_violation(
        self, mocker
    ) -> None:
        mocker.patch(
            "maasservicelayer.services.hardening.is_hardening_enabled",
            return_value=True,
        )
        # Caller passes no cert PEM (e.g. cert read failed at call site).
        result = configure_and_validate_hardening(fips_declared=None)
        assert any(v.code == "MISSING_TLS_CERT" for v in result)
