#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Unit tests for maascommon.hardening — runtime hardening activation."""

import pytest

from maascommon.hardening import (
    get_hardening_config,
    HardeningConfig,
    HardeningMode,
)


@pytest.fixture(autouse=True)
def clear_hardening_cache():
    get_hardening_config.cache_clear()
    yield
    get_hardening_config.cache_clear()


class TestHardeningActive:
    @pytest.mark.parametrize("mode", list(HardeningMode))
    def test_fips_host_active_regardless_of_mode(self, mode):
        # On a FIPS host hardening is always active; `off` cannot disable it.
        config = HardeningConfig(mode=mode, fips_enabled=True)
        assert config.hardening_active is True

    def test_non_fips_on_is_active(self):
        config = HardeningConfig(mode=HardeningMode.ON, fips_enabled=False)
        assert config.hardening_active is True

    @pytest.mark.parametrize("mode", [HardeningMode.AUTO, HardeningMode.OFF])
    def test_non_fips_auto_or_off_is_inactive(self, mode):
        config = HardeningConfig(mode=mode, fips_enabled=False)
        assert config.hardening_active is False


class TestLoad:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("auto", HardeningMode.AUTO),
            ("on", HardeningMode.ON),
            ("off", HardeningMode.OFF),
            ("ON", HardeningMode.ON),
            ("Off", HardeningMode.OFF),
        ],
    )
    def test_parses_mode_case_insensitively(
        self, monkeypatch, value, expected
    ):
        monkeypatch.setattr(
            "maascommon.hardening.is_fips_enabled", lambda: False
        )
        assert HardeningConfig.load(value).mode is expected

    def test_combines_host_fips_state(self, monkeypatch):
        monkeypatch.setattr(
            "maascommon.hardening.is_fips_enabled", lambda: True
        )
        config = HardeningConfig.load("off")
        assert config.fips_enabled is True
        # FIPS host overrides an explicit `off`.
        assert config.hardening_active is True

    def test_invalid_value_raises(self, monkeypatch):
        monkeypatch.setattr(
            "maascommon.hardening.is_fips_enabled", lambda: False
        )
        with pytest.raises(ValueError):
            HardeningConfig.load("bogus")


class TestGetHardeningConfig:
    def test_cached_once_per_process(self, monkeypatch):
        monkeypatch.setattr(
            "maascommon.hardening.is_fips_enabled", lambda: False
        )
        first = get_hardening_config("on")
        second = get_hardening_config("on")
        assert first is second

    def test_never_raises_on_host_fips_state(self, monkeypatch):
        # No startup refusal: a FIPS host must not error out.
        monkeypatch.setattr(
            "maascommon.hardening.is_fips_enabled", lambda: True
        )
        config = get_hardening_config("auto")
        assert config.fips_enabled is True
        assert config.hardening_active is True
