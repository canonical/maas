#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Unit tests for maascommon.hardening — runtime hardening activation."""

import pytest

import maascommon.hardening as _hardening
from maascommon.hardening import configure_hardening, is_hardening_enabled


@pytest.fixture(autouse=True)
def reset_hardening_state():
    """Restore hardening globals after every test."""
    original_active = _hardening._hardening_active
    original_configured = _hardening._hardening_configured
    yield
    _hardening._hardening_active = original_active
    _hardening._hardening_configured = original_configured


class TestConfigureHardening:
    def test_fips_host_activates_regardless_of_setting(self, monkeypatch):
        monkeypatch.setattr(_hardening, "is_fips_enabled", lambda: True)
        configure_hardening("off")
        assert is_hardening_enabled() is True

    def test_explicit_on_activates_on_non_fips_host(self, monkeypatch):
        monkeypatch.setattr(_hardening, "is_fips_enabled", lambda: False)
        configure_hardening("on")
        assert is_hardening_enabled() is True

    def test_auto_is_inactive_on_non_fips_host(self, monkeypatch):
        monkeypatch.setattr(_hardening, "is_fips_enabled", lambda: False)
        configure_hardening("auto")
        assert is_hardening_enabled() is False

    def test_setting_is_case_insensitive(self, monkeypatch):
        monkeypatch.setattr(_hardening, "is_fips_enabled", lambda: False)
        configure_hardening("ON")
        assert is_hardening_enabled() is True

    def test_second_call_is_ignored(self, monkeypatch):
        monkeypatch.setattr(_hardening, "is_fips_enabled", lambda: False)
        configure_hardening("on")
        assert is_hardening_enabled() is True
        configure_hardening("off")
        # Second call must not change the already-configured state.
        assert is_hardening_enabled() is True
