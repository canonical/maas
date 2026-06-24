# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""FIPS-mode validation helpers for power configuration forms."""

from django.core.exceptions import ValidationError

from maascommon.fips import is_fips_enabled
from maascommon.hardening import is_hardening_enabled
from maascommon.validation import validate_password_complexity
from provisioningserver.drivers.power.fips import (
    FIPS_ALLOWED_IPMI_CIPHERS,
    get_fips_compliant_alternatives,
    get_fips_status_for_driver,
)


def validate_power_params_fips(
    power_type: str, power_parameters: dict
) -> None:
    """Raise ValidationError if power parameters violate FIPS requirements.

    Called from AdminMachineForm.clean() and PodForm.clean() when FIPS is
    enabled on the host.  Does nothing when FIPS is not enabled.
    """
    if not is_fips_enabled():
        return

    # Check driver FIPS support
    supported, reason = get_fips_status_for_driver(power_type)
    if not supported:
        alternatives = get_fips_compliant_alternatives()
        raise ValidationError(
            f"Power driver '{power_type}' is not supported in FIPS mode: "
            f"{reason}. FIPS-compliant alternatives: "
            f"{', '.join(sorted(alternatives))}",
            code="fips_violation",
        )

    # IPMI: enforce cipher suite 17
    if power_type == "ipmi":
        cipher = str(power_parameters.get("cipher_suite_id", "17"))
        if cipher not in FIPS_ALLOWED_IPMI_CIPHERS:
            raise ValidationError(
                f"IPMI cipher suite '{cipher}' is not FIPS-approved. "
                "Only cipher suite 17 is permitted.",
                code="fips_violation",
            )

    # Drivers that support verify_ssl: reject verify_ssl=false
    verify_ssl_drivers = {"webhook", "hmcz", "proxmox", "lxd"}
    if power_type in verify_ssl_drivers:
        verify_ssl = power_parameters.get(
            "power_verify_ssl", power_parameters.get("verify_ssl", True)
        )
        # Handle both bool and string 'false'
        if isinstance(verify_ssl, str):
            verify_ssl = verify_ssl.lower() not in ("false", "0", "no")
        if not verify_ssl:
            raise ValidationError(
                f"SSL certificate verification must be enabled for "
                f"'{power_type}' in FIPS mode.",
                code="fips_violation",
            )


def validate_power_pass_complexity(power_parameters: dict) -> None:
    """Raise ValidationError if power_pass fails complexity requirements.

    Only enforced when hardening is active (FIPS host or hardening_enabled=on).
    Does nothing when hardening is not active.
    """
    if not is_hardening_enabled():
        return

    power_pass = power_parameters.get("power_pass", "")
    if not power_pass:  # empty/absent password: skip (driver may not need one)
        return

    result = validate_password_complexity(power_pass)
    if not result.is_valid:
        requirements = "; ".join(result.errors)
        raise ValidationError(
            f"Power credential password does not meet complexity requirements: "
            f"{requirements}",
            code="password_complexity",
        )
