# Copyright 2025 Canonical Ltd.
# SPDX-License-Identifier: AGPL-3.0-only

"""VMware power driver implementation."""

import logging

try:
    from pyVmomi import vim
except ImportError:
    vim = None  # type: ignore[misc,assignment]

logger = logging.getLogger("maas-power-driver-vmware")


class VMwarePowerDriver:
    """VMware power driver using pyvmomi."""

    def _get_si(self, context: dict):
        """Get a VMware ServiceInstance."""
        try:
            from pyVim.connect import SmartConnect
        except ImportError:
            raise RuntimeError("python3-pyvmomi package is not installed")

        power_address = context.get("power_address")
        if not power_address:
            raise ValueError("Missing 'power_address' in context")

        power_user = context.get("power_user", "")
        power_pass = context.get("power_pass", "")

        si = SmartConnect(
            host=power_address,
            user=power_user,
            pwd=power_pass,
        )
        return si

    def _find_vm(self, si, vm_name: str):
        """Find a VM by name."""
        content = si.RetrieveContent()
        container = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True
        )
        for vm in container.view:
            if vm.name == vm_name:
                return vm
        raise RuntimeError(f"VM '{vm_name}' not found")

    def query(self, system_id: str, context: dict) -> str:
        """Query the current power state."""
        si = self._get_si(context)
        try:
            vm_name = context.get("vm_name", "")
            if not vm_name:
                raise ValueError("Missing 'vm_name' in context")

            vm = self._find_vm(si, vm_name)
            if vm.runtime.powerState == "poweredOn":
                return "on"
            elif vm.runtime.powerState == "poweredOff":
                return "off"
            return "unknown"
        except Exception as e:
            logger.error("VMware query failed: %s", e)
            raise
        finally:
            from pyVim.connect import Disconnect
            Disconnect(si)

    def on(self, system_id: str, context: dict) -> None:
        si = self._get_si(context)
        try:
            vm_name = context.get("vm_name", "")
            vm = self._find_vm(si, vm_name)
            vm.PowerOn()
        finally:
            from pyVim.connect import Disconnect
            Disconnect(si)

    def off(self, system_id: str, context: dict) -> None:
        si = self._get_si(context)
        try:
            vm_name = context.get("vm_name", "")
            vm = self._find_vm(si, vm_name)
            task = vm.PowerOff()
            task.wait()
        finally:
            from pyVim.connect import Disconnect
            Disconnect(si)

    def cycle(self, system_id: str, context: dict) -> None:
        self.off(system_id, context)
        self.on(system_id, context)

    def reset(self, system_id: str, context: dict) -> None:
        si = self._get_si(context)
        try:
            vm_name = context.get("vm_name", "")
            vm = self._find_vm(si, vm_name)
            vm.Reset()
        finally:
            from pyVim.connect import Disconnect
            Disconnect(si)

    def set_boot_order(self, system_id: str, context: dict) -> None:
        logger.warning("set_boot_order is not supported by the VMware driver")
