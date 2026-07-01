#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Runtime security-hardening mode determination for MAAS."""

import logging

from maascommon.fips import is_fips_enabled

_logger = logging.getLogger("maas.hardening")

#: Set by configure_hardening() at process startup.
_hardening_active: bool = False


def configure_hardening(hardening_enabled: str) -> None:
    """Set the process-wide hardening state.

    Call exactly once at process startup, before any service reads
    ``is_hardening_enabled()``.  ``hardening_enabled`` is the raw value of the
    ``hardening_enabled`` configuration option: ``"auto"``, ``"on"``, or
    ``"off"`` (case-insensitive).  On a FIPS host hardening is always active
    regardless of the setting; on a non-FIPS host it activates only when
    explicitly set to ``"on"``.
    """
    global _hardening_active
    fips = is_fips_enabled()
    _hardening_active = fips or hardening_enabled.strip().lower() == "on"
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
