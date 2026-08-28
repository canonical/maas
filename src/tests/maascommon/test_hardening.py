#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""Unit tests for maascommon.hardening — runtime hardening activation."""

import pytest

import maascommon.hardening as _hardening
from maascommon.hardening import (
    check_bind_violations,
    configure_hardening,
    HardeningMode,
    is_hardening_enabled,
)


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
        configure_hardening(HardeningMode.OFF)
        assert is_hardening_enabled() is True

    def test_explicit_on_activates_on_non_fips_host(self, monkeypatch):
        monkeypatch.setattr(_hardening, "is_fips_enabled", lambda: False)
        configure_hardening(HardeningMode.ON)
        assert is_hardening_enabled() is True

    def test_auto_is_inactive_on_non_fips_host(self, monkeypatch):
        monkeypatch.setattr(_hardening, "is_fips_enabled", lambda: False)
        configure_hardening(HardeningMode.AUTO)
        assert is_hardening_enabled() is False

    def test_none_is_inactive_on_non_fips_host(self, monkeypatch):
        monkeypatch.setattr(_hardening, "is_fips_enabled", lambda: False)
        configure_hardening(None)
        assert is_hardening_enabled() is False

    def test_second_call_is_ignored(self, monkeypatch):
        monkeypatch.setattr(_hardening, "is_fips_enabled", lambda: False)
        configure_hardening(HardeningMode.ON)
        assert is_hardening_enabled() is True
        configure_hardening(HardeningMode.OFF)
        # Second call must not change the already-configured state.
        assert is_hardening_enabled() is True


class TestCheckBindViolations:
    def test_empty_auto_derived_key_is_not_a_violation(self):
        violations = check_bind_violations(
            {"api_bind": []}, frozenset({"api_bind"}), "maas config-hardening"
        )
        assert violations == []

    def test_empty_non_auto_derived_key_is_a_wildcard_violation(self):
        violations = check_bind_violations(
            {"rpc_bind": []}, frozenset(), "maas config-hardening"
        )
        assert len(violations) == 1
        assert violations[0].code == "WILDCARD_BIND_NOT_ALLOWED"
        assert violations[0].config_key == "rpc_bind"

    def test_explicit_wildcard_address_is_a_violation(self):
        violations = check_bind_violations(
            {"api_bind": ["0.0.0.0"]},
            frozenset({"api_bind"}),
            "maas config-hardening",
        )
        assert len(violations) == 1
        assert violations[0].code == "WILDCARD_BIND_NOT_ALLOWED"

    def test_ipv6_wildcard_address_is_a_violation(self):
        violations = check_bind_violations(
            {"api_bind6": ["::"]},
            frozenset({"api_bind6"}),
            "maas config-hardening",
        )
        assert len(violations) == 1
        assert violations[0].code == "WILDCARD_BIND_NOT_ALLOWED"

    def test_specific_address_is_not_a_violation(self):
        violations = check_bind_violations(
            {"api_bind": ["10.0.0.5"]},
            frozenset({"api_bind"}),
            "maas config-hardening",
        )
        assert violations == []

    def test_invalid_address_wins_over_wildcard_for_same_key(self):
        # A key with one malformed value and one wildcard value reports
        # only the invalid-address finding: once the parser rejects one
        # value the rest of the list cannot be trusted (F8).
        violations = check_bind_violations(
            {"api_bind": ["not-an-ip", "0.0.0.0"]},
            frozenset({"api_bind"}),
            "maas config-hardening",
        )
        assert len(violations) == 1
        assert violations[0].code == "INVALID_BIND_ADDRESS"
        assert "not-an-ip" in violations[0].message

    def test_resolution_uses_command_prefix(self):
        violations = check_bind_violations(
            {"rpc_bind": []}, frozenset(), "maas-rack config-hardening"
        )
        assert violations[0].resolution.startswith(
            "Run: maas-rack config-hardening set rpc_bind"
        )
