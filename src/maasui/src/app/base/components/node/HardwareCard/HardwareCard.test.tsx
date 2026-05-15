import HardwareCard, { Labels as HardwareCardLabels } from "./HardwareCard";

import * as factory from "@/testing/factories";
import { screen, within, renderWithProviders } from "@/testing/utils";

it("renders with system data", () => {
  const machine = factory.machineDetails({ system_id: "abc123" });
  const state = factory.rootState({
    machine: factory.machineState({ items: [machine] }),
  });
  renderWithProviders(<HardwareCard node={machine} />, {
    state,
  });

  const system = screen.getByRole("list", { name: HardwareCardLabels.System });
  const mainboard = screen.getByRole("list", {
    name: HardwareCardLabels.Mainboard,
  });

  const sys_vendor = within(system).getByLabelText(
    HardwareCardLabels.SysVendor
  );
  const sys_product = within(system).getByLabelText(
    HardwareCardLabels.SysProduct
  );
  const sys_version = within(system).getByLabelText(
    HardwareCardLabels.SysVersion
  );
  const serial = within(system).getByLabelText(HardwareCardLabels.Serial);

  const mb_vendor = within(mainboard).getByLabelText(
    HardwareCardLabels.MainboardVendor
  );
  const mb_product = within(mainboard).getByLabelText(
    HardwareCardLabels.MainboardProduct
  );
  const mb_firmware = within(mainboard).getByLabelText(
    HardwareCardLabels.MainboardFirmware
  );
  const bios_mode = within(mainboard).getByLabelText(
    HardwareCardLabels.BiosBootMode
  );
  const mb_version = within(mainboard).getByLabelText(
    HardwareCardLabels.MainboardVersion
  );
  const date = within(mainboard).getByLabelText(HardwareCardLabels.Date);

  expect(sys_vendor).toHaveTextContent("QEMU");
  expect(sys_product).toHaveTextContent("Standard PC (Q35 + ICH9, 2009)");
  expect(sys_version).toHaveTextContent("pc-q35-5.1");
  expect(serial).toHaveTextContent(HardwareCardLabels.Unknown);
  expect(mb_vendor).toHaveTextContent("Canonical Ltd.");
  expect(mb_product).toHaveTextContent("LXD");
  expect(mb_firmware).toHaveTextContent("EFI Development Kit II / OVMF");
  expect(bios_mode).toHaveTextContent("UEFI");
  expect(mb_version).toHaveTextContent("0.0.0");
  expect(date).toHaveTextContent("02/06/2015");
});

it("renders when system data is not available", () => {
  const machine = factory.machineDetails({ metadata: {}, system_id: "abc123" });
  const state = factory.rootState({
    machine: factory.machineState({ items: [machine] }),
  });
  renderWithProviders(<HardwareCard node={machine} />, {
    state,
  });

  // Machine still has a BIOS boot mode, so we're looking for 9 instead of 10
  expect(screen.getAllByText(HardwareCardLabels.Unknown).length).toBe(9);
});
