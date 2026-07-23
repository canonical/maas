#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Startup hardening validation for MAAS service-layer.

Validates TLS certificates, DH parameters, service bindings, and database
SSL mode at region/rack startup.  Activated only when
``is_hardening_enabled()`` returns True (FIPS host or explicit opt-in).

Violations are returned as a list of :class:`HardeningViolation` objects.
The validator never raises, exits, or blocks socket binding.
"""

from dataclasses import dataclass, field
import ipaddress
import logging
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_parameters

from maascommon.fips import is_fips_enabled
from maascommon.hardening import is_hardening_enabled

_log = logging.getLogger("maas.hardening")

_INSECURE_SSLMODES = frozenset({"disable", "allow", "prefer", "require"})


def _ident(code: str) -> str:
    slug = code.lower().replace("_", "-")[:29]
    return f"hardening-{slug}"


@dataclass(frozen=True)
class HardeningViolation:
    """A single hardening validation failure."""

    ident: str
    code: str
    message: str
    resolution: str
    config_key: str
    file_path: str | None = field(default=None)


def _violation(
    code: str,
    message: str,
    resolution: str,
    config_key: str,
    file_path: str | None = None,
    ident: str | None = None,
) -> HardeningViolation:
    return HardeningViolation(
        ident=ident if ident is not None else _ident(code),
        code=code,
        message=message,
        resolution=resolution,
        config_key=config_key,
        file_path=file_path,
    )


class HardeningValidator:
    """Validates hardening prerequisites at service startup."""

    def __init__(
        self,
        hardening_active: bool,
        api_tls_cert_pem: bytes | None = None,
        api_tls_key_pem: bytes | None = None,
        api_tls_dhparam: str | None = None,
        api_bind: str | None = None,
        api_bind6: str | None = None,
        prometheus_bind: str | None = None,
        temporal_bind: str | None = None,
        rpc_bind: str | None = None,
        dns_bind: str | None = None,
        database_sslmode: str | None = None,
        fips_declared: bool | None = None,
        fips_active: bool = False,
    ) -> None:
        self.hardening_active = hardening_active
        self.api_tls_cert_pem = api_tls_cert_pem
        self.api_tls_key_pem = api_tls_key_pem
        self.api_tls_dhparam = api_tls_dhparam
        self._binds: dict[str, str | None] = {
            "api_bind": api_bind,
            "api_bind6": api_bind6,
            "prometheus_bind": prometheus_bind,
            "temporal_bind": temporal_bind,
            "rpc_bind": rpc_bind,
            "dns_bind": dns_bind,
        }
        self.database_sslmode = database_sslmode
        self.fips_declared = fips_declared
        self.fips_active = fips_active

    def validate(self) -> list[HardeningViolation]:
        violations: list[HardeningViolation] = []

        try:
            violations += self._validate_fips_drift()
        except Exception as exc:  # noqa: BLE001
            _log.warning("hardening: _validate_fips_drift raised: %s", exc)

        if not self.hardening_active:
            return violations

        for check in (
            self._validate_tls_cert,
            self._validate_dh_params,
            self._validate_bindings,
            self._validate_db_sslmode,
        ):
            try:
                violations += check()
            except Exception as exc:  # noqa: BLE001
                _log.warning("hardening: %s raised: %s", check.__name__, exc)

        for v in violations:
            _log.error(
                "hardening_violation: ident=%s code=%s config_key=%s file_path=%s message=%s",
                v.ident,
                v.code,
                v.config_key,
                v.file_path,
                v.message,
            )

        return violations

    def _validate_tls_cert(self) -> list[HardeningViolation]:
        if self.api_tls_cert_pem is None:
            return [
                _violation(
                    code="MISSING_TLS_CERT",
                    message="TLS certificate is not configured",
                    resolution="Run: maas config-tls enable <key> <cert>",
                    config_key="tls",
                )
            ]

        if self.api_tls_key_pem is None:
            return [
                _violation(
                    code="MISSING_TLS_KEY",
                    message="TLS private key is not configured",
                    resolution="Run: maas config-tls enable <key> <cert>",
                    config_key="tls",
                )
            ]

        try:
            cert = x509.load_pem_x509_certificate(self.api_tls_cert_pem)
            key = serialization.load_pem_private_key(
                self.api_tls_key_pem, password=None
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
                return [
                    _violation(
                        code="TLS_CERT_KEY_MISMATCH",
                        message="TLS certificate and private key do not match",
                        resolution="Run: maas config-tls enable <key> <cert> with a matching pair",
                        config_key="tls",
                    )
                ]
        except Exception as exc:
            return [
                _violation(
                    code="TLS_CERT_PARSE_ERROR",
                    message=f"Failed to parse TLS certificate or key: {exc}",
                    resolution="Run: maas config-tls enable <key> <cert> with a valid PEM certificate",
                    config_key="tls",
                )
            ]

        return []

    def _validate_dh_params(self) -> list[HardeningViolation]:
        if not self.api_tls_dhparam:
            return []

        dhparam_path = Path(self.api_tls_dhparam)
        if not dhparam_path.exists():
            return []

        try:
            dh_params = load_pem_parameters(dhparam_path.read_bytes())
            bit_length = dh_params.parameter_numbers().p.bit_length()
            if bit_length < 2048:
                return [
                    _violation(
                        code="WEAK_DH_PARAMS",
                        message=f"DH parameters are {bit_length} bits; minimum is 2048",
                        resolution="Run: openssl dhparam -out dhparam.pem 2048, then run: maas config-hardening set api_tls_dhparam=<path>",
                        config_key="api_tls_dhparam",
                        file_path=str(dhparam_path),
                    )
                ]
        except Exception as exc:
            return [
                _violation(
                    code="DH_PARAMS_PARSE_ERROR",
                    message=f"Failed to parse DH parameters file: {exc}",
                    resolution="Run: maas config-hardening set api_tls_dhparam=<path> pointing to a valid PEM DH parameters file",
                    config_key="api_tls_dhparam",
                    file_path=str(dhparam_path),
                )
            ]

        return []

    def _validate_bindings(self) -> list[HardeningViolation]:
        """Per-key wildcard/empty check; each key clears independently."""
        violations: list[HardeningViolation] = []

        for key, value in self._binds.items():
            if not value:
                violations.append(
                    self._wildcard_bind_violation(
                        key,
                        "is not configured; the service would bind to all interfaces",
                    )
                )
                continue
            try:
                addr = ipaddress.ip_address(value)
            except ValueError:
                violations.append(
                    _violation(
                        code="INVALID_BIND_ADDRESS",
                        message=f"{key} '{value}' is not a valid IP address",
                        resolution=(
                            f"Run: maas config-hardening set {key} "
                            f"<specific-ip-address>"
                        ),
                        config_key=key,
                    )
                )
                continue
            if addr.is_unspecified:
                violations.append(
                    self._wildcard_bind_violation(
                        key, f"'{value}' binds to all interfaces"
                    )
                )

        return violations

    @staticmethod
    def _wildcard_bind_violation(key: str, detail: str) -> HardeningViolation:
        return _violation(
            code="WILDCARD_BIND_NOT_ALLOWED",
            message=(
                f"{key} {detail}, which is not allowed when hardening is active"
            ),
            resolution=(
                f"Run: maas config-hardening set {key} <specific-ip-address>"
            ),
            config_key=key,
            ident=f"hardening-wildcard-bind-{key.replace('_', '-')}",
        )

    def _validate_fips_drift(self) -> list[HardeningViolation]:
        # Only flag when the operator declared FIPS in the DB but the kernel
        # disagrees.  The reverse (kernel FIPS, config silent) is not flagged
        # here because hardening.py already activates all FIPS controls via
        # is_fips_enabled() regardless of what the DB says.
        if not self.fips_declared or self.fips_declared == self.fips_active:
            return []
        return [
            _violation(
                code="FIPS_CONFIG_STATUS_MISMATCH",
                message=(
                    "FIPS is declared enabled in configuration but the "
                    "host kernel does not have FIPS mode active "
                    "(/proc/sys/crypto/fips_enabled != 1). "
                    "FIPS-conditional controls are not active."
                ),
                resolution=(
                    "Run: maas config-hardening set fips_enabled false"
                    "  (or re-enable FIPS on the host)"
                ),
                config_key="fips_enabled",
                ident="hardening-fips-config-mismatch",
            )
        ]

    def _validate_db_sslmode(self) -> list[HardeningViolation]:
        if not self.database_sslmode:
            return []
        if self.database_sslmode.lower() in _INSECURE_SSLMODES:
            return [
                _violation(
                    code="INSECURE_DB_SSLMODE",
                    message=f"database_sslmode '{self.database_sslmode}' does not verify the server certificate",
                    resolution="Set database_sslmode=verify-full in regiond.conf (and supply database_sslcert, database_sslkey, database_sslrootcert)",
                    config_key="database_sslmode",
                )
            ]
        return []


def configure_and_validate_hardening(
    *,
    api_tls_cert_pem: bytes | None = None,
    api_tls_key_pem: bytes | None = None,
    api_tls_dhparam: str = "",
    api_bind: str = "",
    api_bind6: str = "",
    prometheus_bind: str = "",
    temporal_bind: str = "",
    rpc_bind: str = "",
    dns_bind: str = "",
    database_sslmode: str = "",
    fips_declared: bool | None = None,
) -> list[HardeningViolation]:
    """Run hardening validation.

    ``api_tls_cert_pem`` and ``api_tls_key_pem`` are optional PEM bytes for
    the TLS certificate/key; the caller is responsible for reading them from
    the secrets store.  Returns violations.  Never raises or exits.
    """
    validator = HardeningValidator(
        hardening_active=is_hardening_enabled(),
        api_tls_cert_pem=api_tls_cert_pem,
        api_tls_key_pem=api_tls_key_pem,
        api_tls_dhparam=api_tls_dhparam or None,
        api_bind=api_bind or None,
        api_bind6=api_bind6 or None,
        prometheus_bind=prometheus_bind or None,
        temporal_bind=temporal_bind or None,
        rpc_bind=rpc_bind or None,
        dns_bind=dns_bind or None,
        database_sslmode=database_sslmode or None,
        fips_declared=fips_declared,
        fips_active=is_fips_enabled(),
    )
    return validator.validate()
