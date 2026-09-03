#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Runtime security-hardening mode determination for MAAS."""

from dataclasses import dataclass
from enum import StrEnum
import ipaddress
import logging

from maascommon.fips import is_fips_enabled

_logger = logging.getLogger("maas.hardening")

#: Set by configure_hardening() at process startup.
_hardening_active: bool = False
_hardening_configured: bool = False


class HardeningMode(StrEnum):
    AUTO = "auto"
    ON = "on"
    OFF = "off"


#: regiond.conf-backed hardening parameters managed by
#: ``maas config-hardening`` (see ``maasserver.config``).
CONF_KEYS = frozenset(
    {
        "api_tls_dhparam",
        "api_bind",
        "api_bind6",
        "prometheus_bind",
        "temporal_bind",
        "rpc_bind",
        "agent_api_bind",
        "agent_api_bind6",
        "dns_bind",
        "dns_bind6",
        "syslog_bind",
        "http_proxy_bind",
        "http_proxy_bind6",
        "database_sslmode",
        "database_sslcert",
        "database_sslkey",
        "database_sslrootcert",
    }
)

#: Subset of :data:`CONF_KEYS` backed by a comma-separated list in
#: regiond.conf (see ``ForEach`` in ``maasserver.config``). Every other
#: conf-backed key is a plain scalar string.
CONF_LIST_KEYS = frozenset(
    {
        "api_bind",
        "api_bind6",
        "rpc_bind",
        "agent_api_bind",
        "agent_api_bind6",
        "dns_bind",
        "dns_bind6",
        "syslog_bind",
        "http_proxy_bind",
        "http_proxy_bind6",
    }
)


def configure_hardening(hardening_enabled: HardeningMode | None) -> None:
    """Set the process-wide hardening state.

    Must be called once at process startup, before any service reads
    ``is_hardening_enabled()``.  Subsequent calls are no-ops (the value
    is stable for the process lifetime).  ``hardening_enabled`` is the raw
    value of the ``hardening_enabled`` configuration option: ``"auto"``,
    ``"on"``, or ``"off"`` (case-insensitive), or ``None`` when the row
    is absent from the DB (treated the same as ``"auto"``).  On a FIPS host
    hardening is always active regardless of the setting; on a non-FIPS host
    it activates only when explicitly set to ``"on"``.
    """
    global _hardening_active, _hardening_configured
    if _hardening_configured:
        _logger.debug(
            "configure_hardening called again (setting=%s); ignoring — "
            "hardening state is fixed for this process lifetime.",
            hardening_enabled,
        )
        return
    fips = is_fips_enabled()
    _hardening_active = fips or hardening_enabled == HardeningMode.ON
    _hardening_configured = True
    _logger.info(
        "hardening_mode_determined: setting=%s fips_enabled=%s "
        "hardening_active=%s",
        hardening_enabled,
        fips,
        _hardening_active,
    )


def is_hardening_enabled() -> bool:
    """Return True when hardening is active for this process."""
    return _hardening_active


@dataclass(frozen=True)
class BindViolation:
    """A single hardening validation failure.

    Shared between the region (`maasservicelayer.services.hardening`,
    where it is re-exported as ``HardeningViolation``) and the rack
    (`provisioningserver.hardening_command`). Bind-key checks populate
    every field except ``file_path``; region-only checks (TLS
    certificate, DH parameters) use ``file_path`` to point at the
    offending file on disk.
    """

    code: str
    message: str
    resolution: str
    config_key: str
    ident: str
    file_path: str | None = None


def _wildcard_bind_violation(
    key: str, detail: str, command_prefix: str
) -> BindViolation:
    return BindViolation(
        code="WILDCARD_BIND_NOT_ALLOWED",
        message=(
            f"{key} {detail}, which is not allowed when hardening is active"
        ),
        resolution=f"Run: {command_prefix} set {key} <specific-ip-address>",
        config_key=key,
        ident=f"hardening-wildcard-bind-{key.replace('_', '-')}",
    )


def check_bind_violations(
    binds: dict[str, list[str]],
    auto_derived_keys: frozenset[str],
    command_prefix: str,
) -> list[BindViolation]:
    """Per-key wildcard/empty/invalid-address check.

    A key with at least one malformed address is reported as one
    ``INVALID_BIND_ADDRESS`` violation per bad value and nothing else for
    that key: once a value fails to parse, the rest of the list cannot be
    trusted, so the wildcard check is skipped rather than layering an
    unreliable second finding on top (the invalid-address finding wins).

    ``auto_derived_keys`` are keys whose empty value resolves to a
    specific, non-wildcard address elsewhere at runtime (e.g. derived from
    ``maas_url``), so leaving them unset is not itself a violation.
    ``command_prefix`` names the CLI invocation quoted in each resolution
    string (``maas config-hardening`` on the region, ``maas-rack
    config-hardening`` on the rack).
    """
    violations: list[BindViolation] = []
    for key, values in binds.items():
        values = list(values) if values else []
        if not values:
            if key in auto_derived_keys:
                continue
            violations.append(
                _wildcard_bind_violation(
                    key,
                    "is not configured; the service would bind to all interfaces",
                    command_prefix,
                )
            )
            continue

        invalid_values = []
        wildcard_values = []
        for value in values:
            try:
                addr = ipaddress.ip_address(value)
            except ValueError:
                invalid_values.append(value)
                continue
            if addr.is_unspecified:
                wildcard_values.append(value)

        if invalid_values:
            for value in invalid_values:
                violations.append(
                    BindViolation(
                        code="INVALID_BIND_ADDRESS",
                        message=f"{key} '{value}' is not a valid IP address",
                        resolution=(
                            f"Run: {command_prefix} set {key} "
                            f"<specific-ip-address>"
                        ),
                        config_key=key,
                        ident=f"hardening-invalid-bind-{key.replace('_', '-')}",
                    )
                )
            continue

        for value in wildcard_values:
            violations.append(
                _wildcard_bind_violation(
                    key, f"'{value}' binds to all interfaces", command_prefix
                )
            )

    return violations
