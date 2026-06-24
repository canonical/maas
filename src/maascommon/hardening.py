#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Runtime security-hardening mode determination for MAAS."""

import logging

from maascommon.fips import is_fips_enabled

_logger = logging.getLogger("maas.hardening")

#: Set by configure_hardening() at process startup.
_hardening_active: bool = False
_hardening_configured: bool = False


def configure_hardening(hardening_enabled: "str | None") -> None:
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
    _hardening_active = (
        fips or (hardening_enabled or "").strip().lower() == "on"
    )
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
