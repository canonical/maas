# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the Proxmox power driver."""

import pytest

from maas_power_driver_proxmox.driver import ProxmoxPowerDriver


@pytest.fixture
def driver():
    """Create a fresh ProxmoxPowerDriver instance."""
    return ProxmoxPowerDriver()


class TestProxmoxPowerDriver:
    """Tests for ProxmoxPowerDriver methods."""

    def test_query_raises_not_implemented(self, driver):
        """query() should raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            driver.query("sys1", {"power_address": "10.0.0.1"})

    def test_query_missing_power_address(self, driver):
        """query() should raise ValueError without power_address."""
        with pytest.raises(ValueError, match="power_address"):
            driver.query("sys1", {})

    def test_on_raises_not_implemented(self, driver):
        """on() should raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            driver.on("sys1", {"power_address": "10.0.0.1"})

    def test_on_missing_power_address(self, driver):
        """on() should raise ValueError without power_address."""
        with pytest.raises(ValueError, match="power_address"):
            driver.on("sys1", {})

    def test_off_raises_not_implemented(self, driver):
        """off() should raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            driver.off("sys1", {"power_address": "10.0.0.1"})

    def test_off_missing_power_address(self, driver):
        """off() should raise ValueError without power_address."""
        with pytest.raises(ValueError, match="power_address"):
            driver.off("sys1", {})

    def test_cycle_raises_not_implemented(self, driver):
        """cycle() should raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            driver.cycle("sys1", {"power_address": "10.0.0.1"})

    def test_reset_raises_not_implemented(self, driver):
        """reset() should raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            driver.reset("sys1", {"power_address": "10.0.0.1"})

    def test_set_boot_order_raises_not_implemented(self, driver):
        """set_boot_order() should raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            driver.set_boot_order("sys1", {"power_address": "10.0.0.1"})
