#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Startup hardening validation for MAAS service-layer.

Validates TLS certificates, DH parameters, and key file permissions before
services open their listening sockets. Activated only when
``is_hardening_enabled()`` returns True (FIPS host or explicit opt-in).
"""

from dataclasses import dataclass
import logging
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_parameters

from maascommon.hardening import is_hardening_enabled


@dataclass
class HardeningError:
    """A single hardening validation failure."""

    code: str
    message: str
    resolution: str
    config_key: str
    file_path: str | None = None


@dataclass
class HardeningValidationResult:
    """Aggregate result of all hardening checks."""

    is_valid: bool
    errors: list[HardeningError]
    warnings: list[str]


class HardeningValidator:
    """Validates hardening prerequisites at service startup."""

    def __init__(
        self,
        hardening_active: bool,
        api_tls_cert: str | None = None,
        api_tls_key: str | None = None,
        api_tls_dhparam: str | None = None,
        api_bind: str | None = None,
    ) -> None:
        self.hardening_active = hardening_active
        self.api_tls_cert = api_tls_cert
        self.api_tls_key = api_tls_key
        self.api_tls_dhparam = api_tls_dhparam
        self.api_bind = api_bind

    def validate(self) -> HardeningValidationResult:
        """Run all hardening checks and return the aggregated result."""
        if not self.hardening_active:
            return HardeningValidationResult(
                is_valid=True, errors=[], warnings=[]
            )

        errors: list[HardeningError] = []
        warnings: list[str] = []

        errors.extend(self._validate_tls_cert())
        errors.extend(self._validate_dh_params())
        errors.extend(self._validate_key_permissions())
        errors.extend(self._validate_bindings())

        return HardeningValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _validate_tls_cert(self) -> list[HardeningError]:
        """Verify TLS certificate and key exist and form a matching pair."""
        errors: list[HardeningError] = []

        if self.api_tls_cert is None:
            return errors

        cert_path = Path(self.api_tls_cert)

        if not cert_path.exists():
            errors.append(
                HardeningError(
                    code="MISSING_TLS_CERT",
                    message=f"TLS certificate not found at {cert_path}",
                    resolution=(
                        f"Create or copy a TLS certificate to {cert_path}"
                    ),
                    config_key="api_tls_cert",
                    file_path=str(cert_path),
                )
            )
            return errors

        if self.api_tls_key is None:
            errors.append(
                HardeningError(
                    code="MISSING_TLS_KEY",
                    message="TLS private key path is not configured",
                    resolution=(
                        "Set api_tls_key in the configuration to the path"
                        " of the TLS private key file"
                    ),
                    config_key="api_tls_key",
                )
            )
            return errors

        key_path = Path(self.api_tls_key)

        if not key_path.exists():
            errors.append(
                HardeningError(
                    code="MISSING_TLS_KEY",
                    message=f"TLS key not found at {key_path}",
                    resolution=(
                        f"Create or copy a TLS private key to {key_path}"
                    ),
                    config_key="api_tls_key",
                    file_path=str(key_path),
                )
            )
            return errors

        try:
            cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
            key = serialization.load_pem_private_key(
                key_path.read_bytes(), password=None
            )
            cert_pub = cert.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            key_pub = key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            if cert_pub != key_pub:
                errors.append(
                    HardeningError(
                        code="TLS_CERT_KEY_MISMATCH",
                        message=(
                            "TLS certificate and private key do not match"
                        ),
                        resolution=(
                            "Ensure the certificate and key are a matching pair"
                        ),
                        config_key="api_tls_cert",
                    )
                )
        except Exception as exc:
            errors.append(
                HardeningError(
                    code="TLS_CERT_PARSE_ERROR",
                    message=(f"Failed to parse TLS certificate or key: {exc}"),
                    resolution="Ensure files are valid PEM format",
                    config_key="api_tls_cert",
                )
            )

        return errors

    def _validate_dh_params(self) -> list[HardeningError]:
        """Verify DH parameters file is present and has >= 2048-bit key."""
        errors: list[HardeningError] = []

        if not self.api_tls_dhparam:
            return errors

        dhparam_path = Path(self.api_tls_dhparam)

        if not dhparam_path.exists():
            return errors

        try:
            dh_params = load_pem_parameters(dhparam_path.read_bytes())
            bit_length = dh_params.parameter_numbers().p.bit_length()
            if bit_length < 2048:
                errors.append(
                    HardeningError(
                        code="WEAK_DH_PARAMS",
                        message=(
                            f"DH parameters are {bit_length} bits; "
                            "minimum is 2048"
                        ),
                        resolution=(
                            "Regenerate DH parameters with at least 2048 bits:"
                            " openssl dhparam -out dhparam.pem 2048"
                        ),
                        config_key="api_tls_dhparam",
                        file_path=str(dhparam_path),
                    )
                )
        except Exception as exc:
            errors.append(
                HardeningError(
                    code="DH_PARAMS_PARSE_ERROR",
                    message=f"Failed to parse DH parameters file: {exc}",
                    resolution=(
                        "Ensure the file is a valid PEM DH parameters file"
                    ),
                    config_key="api_tls_dhparam",
                    file_path=str(dhparam_path),
                )
            )

        return errors

    def _validate_key_permissions(self) -> list[HardeningError]:
        """Verify the TLS private key file has permissions <= 0o600."""
        errors: list[HardeningError] = []

        if not self.api_tls_key:
            return errors

        key_path = Path(self.api_tls_key)

        if not key_path.exists():
            return errors

        mode = os.stat(key_path).st_mode & 0o777
        if mode > 0o600:
            errors.append(
                HardeningError(
                    code="INSECURE_KEY_PERMISSIONS",
                    message=(
                        f"TLS key file {key_path} has insecure permissions"
                        f" {oct(mode)}"
                    ),
                    resolution=f"chmod 600 {key_path}",
                    config_key="api_tls_key",
                    file_path=str(key_path),
                )
            )

        return errors

    def _validate_bindings(self) -> list[HardeningError]:
        """Verify api_bind is a valid IP address when specified."""
        import ipaddress

        errors: list[HardeningError] = []

        if not self.api_bind:
            return errors

        try:
            ipaddress.ip_address(self.api_bind)
        except ValueError:
            errors.append(
                HardeningError(
                    code="INVALID_BIND_ADDRESS",
                    message=(
                        f"api_bind '{self.api_bind}' is not a valid IP address"
                    ),
                    resolution=(
                        "Set api_bind to a valid IPv4 or IPv6 address,"
                        " e.g. '0.0.0.0' or '::'."
                    ),
                    config_key="api_bind",
                )
            )

        return errors


def run_hardening_startup_validation(
    *,
    api_tls_cert: str = "",
    api_tls_key: str = "",
    api_tls_dhparam: str = "",
    api_bind: str = "",
) -> HardeningValidationResult:
    """Run hardening startup validation; raise SystemExit(1) on failure.

    No-op when hardening is inactive. Logs each error via
    ``maas.hardening`` and raises ``SystemExit(1)`` if any check fails.
    Sockets must not be opened before this returns.
    """

    validator = HardeningValidator(
        hardening_active=is_hardening_enabled(),
        api_tls_cert=api_tls_cert,
        api_tls_key=api_tls_key,
        api_tls_dhparam=api_tls_dhparam,
        api_bind=api_bind,
    )
    result = validator.validate()
    if not result.is_valid:
        for error in result.errors:
            logging.getLogger("maas.hardening").error(
                "hardening_validation_failed: code=%s message=%s "
                "resolution=%s config_key=%s file_path=%s",
                error.code,
                error.message,
                error.resolution,
                error.config_key,
                error.file_path,
            )
        raise SystemExit(1)
    return result
