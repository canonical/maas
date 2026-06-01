#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""FIPS compliance classification for MAAS power drivers."""

from enum import Enum

import structlog

from maascommon.fips import is_fips_enabled
from maascommon.logging.security import FIPS_CRYPTO_ERROR, FIPS_DRIVER_REJECTED

logger = structlog.getLogger()


class DriverFIPSStatus(str, Enum):
    """FIPS compliance classification for a power driver."""

    COMPLIANT = "compliant"
    UNSUPPORTED_IN_FIPS = "unsupported_in_fips"


# Maps driver name → (DriverFIPSStatus, reason string)
# reason is None for COMPLIANT, a human-readable string for
# UNSUPPORTED_IN_FIPS.
DRIVER_FIPS_REGISTRY: dict[str, tuple[DriverFIPSStatus, str | None]] = {
    "redfish": (DriverFIPSStatus.COMPLIANT, None),
    "openbmc": (DriverFIPSStatus.COMPLIANT, None),
    "manual": (DriverFIPSStatus.COMPLIANT, None),
    "ipmi": (DriverFIPSStatus.COMPLIANT, None),
    "vmware": (DriverFIPSStatus.COMPLIANT, None),
    "amt": (DriverFIPSStatus.COMPLIANT, None),
    "hmc": (DriverFIPSStatus.COMPLIANT, None),
    "mscm": (DriverFIPSStatus.COMPLIANT, None),
    "wedge": (DriverFIPSStatus.COMPLIANT, None),
    "hmcz": (DriverFIPSStatus.COMPLIANT, None),
    "proxmox": (DriverFIPSStatus.COMPLIANT, None),
    "webhook": (DriverFIPSStatus.COMPLIANT, None),
    "apc": (
        DriverFIPSStatus.UNSUPPORTED_IN_FIPS,
        "Uses SNMPv1 which does not support FIPS-approved authentication",
    ),
    "eaton": (
        DriverFIPSStatus.UNSUPPORTED_IN_FIPS,
        "Uses SNMPv1 which does not support FIPS-approved authentication",
    ),
    "raritan": (
        DriverFIPSStatus.UNSUPPORTED_IN_FIPS,
        "Uses SNMPv2c which does not support FIPS-approved authentication",
    ),
    "dli": (
        DriverFIPSStatus.UNSUPPORTED_IN_FIPS,
        "Uses plain HTTP with no encryption",
    ),
    "msftocs": (
        DriverFIPSStatus.UNSUPPORTED_IN_FIPS,
        "Uses plain HTTP with no encryption",
    ),
    "recs": (
        DriverFIPSStatus.UNSUPPORTED_IN_FIPS,
        "Uses plain HTTP with no encryption",
    ),
    "seamicro": (
        DriverFIPSStatus.UNSUPPORTED_IN_FIPS,
        "Uses plain HTTP with no encryption",
    ),
    "ucsm": (
        DriverFIPSStatus.UNSUPPORTED_IN_FIPS,
        "Uses plain HTTP XML API with no encryption",
    ),
    "moonshot": (
        DriverFIPSStatus.UNSUPPORTED_IN_FIPS,
        "Uses IPMI cipher suites incompatible with FIPS 140-2",
    ),
}

DRIVER_FIPS_REGISTRY.update(
    {
        "recs_box": DRIVER_FIPS_REGISTRY["recs"],
        "sm15k": DRIVER_FIPS_REGISTRY["seamicro"],
    }
)


class FIPSDriverUnsupportedError(Exception):
    """Raised when a FIPS-unsupported driver is invoked in FIPS mode."""


def enforce_tls_verification(driver_name: str, verify_ssl: bool) -> None:
    """Raise PowerFatalError if TLS verification is disabled in FIPS mode."""
    if is_fips_enabled() and not verify_ssl:
        from provisioningserver.drivers.power import PowerFatalError

        logger.error(
            FIPS_CRYPTO_ERROR,
            driver=driver_name,
            operation="tls_connection",
            reason="TLS certificate verification is required in FIPS mode",
        )
        raise PowerFatalError(
            "TLS certificate verification (verify_ssl) is required in "
            f"FIPS mode for the {driver_name} driver. Set "
            "power_verify_ssl to true."
        )


def reject_if_fips_unsupported(driver_name: str) -> None:
    """Raise FIPSDriverUnsupportedError if the driver is not FIPS-compliant."""
    if not is_fips_enabled():
        return
    status, reason = DRIVER_FIPS_REGISTRY.get(
        driver_name,
        (
            DriverFIPSStatus.UNSUPPORTED_IN_FIPS,
            "Driver not listed in FIPS registry",
        ),
    )
    if status != DriverFIPSStatus.UNSUPPORTED_IN_FIPS:
        return
    logger.error(
        FIPS_DRIVER_REJECTED,
        driver=driver_name,
        reason=reason,
    )
    raise FIPSDriverUnsupportedError(
        f"Power driver '{driver_name}' is not supported in FIPS mode: {reason}"
    )
