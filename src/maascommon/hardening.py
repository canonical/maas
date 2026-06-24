#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Runtime security-hardening mode determination for MAAS."""

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
import logging

from maascommon.fips import is_fips_enabled


class HardeningMode(Enum):
    """Operator setting for the ``hardening_enabled`` configuration option."""

    AUTO = "auto"
    ON = "on"
    OFF = "off"


@dataclass(frozen=True)
class HardeningConfig:
    """Resolved hardening activation state for the current process."""

    mode: HardeningMode
    fips_enabled: bool

    @property
    def hardening_active(self) -> bool:
        """Option A: auto-on when the host is in FIPS mode; opt-in otherwise.

        On a FIPS host hardening is always active and ``off`` cannot disable
        it. On a non-FIPS host hardening activates only when explicitly set to
        ``on``.
        """
        if self.fips_enabled:
            return True
        return self.mode == HardeningMode.ON

    @classmethod
    def load(cls, config_hardening_enabled: str = "auto") -> "HardeningConfig":
        """Build from the ``hardening_enabled`` setting and host FIPS state."""
        return cls(
            mode=HardeningMode(config_hardening_enabled.lower()),
            fips_enabled=is_fips_enabled(),
        )


#: Process-wide hardening setting, stored by ``configure_hardening`` at startup.
_hardening_setting: str = "auto"


def configure_hardening(config_hardening_enabled: str) -> "HardeningConfig":
    """Set the process-wide hardening setting and prime the cache.

    Call exactly once at process startup, before any service reads
    ``is_hardening_enabled()`` or ``get_hardening_config()``.
    """
    global _hardening_setting
    _hardening_setting = config_hardening_enabled
    get_hardening_config.cache_clear()
    return get_hardening_config()


@lru_cache(maxsize=1)
def get_hardening_config() -> HardeningConfig:
    """Return the process-wide hardening config, computed once and cached.

    Reads the setting stored by ``configure_hardening`` (defaults to ``auto``
    when called before startup priming), logs the resolved activation once,
    then caches the result for the process lifetime.
    """
    config = HardeningConfig.load(_hardening_setting)
    logging.getLogger("maas.hardening").info(
        "hardening_mode_determined: mode=%s fips_enabled=%s "
        "hardening_active=%s",
        config.mode.value,
        config.fips_enabled,
        config.hardening_active,
    )
    return config


def is_hardening_enabled() -> bool:
    """Return True when hardening is active for this process."""
    return get_hardening_config().hardening_active
