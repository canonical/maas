#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum


class DriverFIPSStatus(Enum):
    COMPLIANT = "compliant"
    UNSUPPORTED = "unsupported"


# FIPS-approved IPMI cipher suites. Cipher 17 is the only suite with
# FIPS-approved integrity, authentication, and confidentiality algorithms
# (HMAC-SHA256 + AES-CBC-128). Per the IPMI spec, cipher 0 disables all
# encryption; any cipher that uses SHA-1, MD5, or weak RSA is non-FIPS.
FIPS_ALLOWED_IPMI_CIPHERS: frozenset[str] = frozenset({"17"})


DRIVER_FIPS_REGISTRY = {
    "amt": (DriverFIPSStatus.COMPLIANT, None),
    "hmc": (DriverFIPSStatus.COMPLIANT, None),
    "hmcz": (DriverFIPSStatus.COMPLIANT, None),
    "ipmi": (DriverFIPSStatus.COMPLIANT, None),
    "manual": (DriverFIPSStatus.COMPLIANT, None),
    "mscm": (DriverFIPSStatus.COMPLIANT, None),
    "nova": (DriverFIPSStatus.COMPLIANT, None),
    "openbmc": (DriverFIPSStatus.COMPLIANT, None),
    "proxmox": (DriverFIPSStatus.COMPLIANT, None),
    "redfish": (DriverFIPSStatus.COMPLIANT, None),
    "virsh": (DriverFIPSStatus.COMPLIANT, None),
    "vmware": (DriverFIPSStatus.COMPLIANT, None),
    "webhook": (DriverFIPSStatus.COMPLIANT, None),
    "wedge": (DriverFIPSStatus.COMPLIANT, None),
    "apc": (
        DriverFIPSStatus.UNSUPPORTED,
        "SNMPv1 — no FIPS-approved authentication",
    ),
    "dli": (DriverFIPSStatus.UNSUPPORTED, "Plain HTTP basic auth"),
    "eaton": (
        DriverFIPSStatus.UNSUPPORTED,
        "SNMPv1 — no FIPS-approved authentication",
    ),
    "moonshot": (
        DriverFIPSStatus.UNSUPPORTED,
        "IPMI without Cipher Suite 17 support",
    ),
    "msftocs": (DriverFIPSStatus.UNSUPPORTED, "Plain HTTP basic auth"),
    "raritan": (
        DriverFIPSStatus.UNSUPPORTED,
        "SNMPv2c — community string only",
    ),
    "recs_box": (DriverFIPSStatus.UNSUPPORTED, "Plain HTTP — no TLS"),
    "sm15k": (DriverFIPSStatus.UNSUPPORTED, "Plain HTTP — no TLS"),
    "ucsm": (DriverFIPSStatus.UNSUPPORTED, "HTTP XML API — no TLS"),
}


def get_fips_status_for_driver(driver_name: str) -> tuple[bool, str | None]:
    status, reason = DRIVER_FIPS_REGISTRY.get(
        driver_name,
        (
            DriverFIPSStatus.UNSUPPORTED,
            "Unknown driver — FIPS compliance not verified",
        ),
    )
    return status == DriverFIPSStatus.COMPLIANT, reason


def get_fips_compliant_alternatives() -> list[str]:
    return [
        name
        for name, (status, _) in DRIVER_FIPS_REGISTRY.items()
        if status == DriverFIPSStatus.COMPLIANT
    ]
