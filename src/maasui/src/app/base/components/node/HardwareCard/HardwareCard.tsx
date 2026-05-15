import { Card } from "@canonical/react-components";

import LabelledList from "@/app/base/components/LabelledList";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";

type Props = {
  node: ControllerDetails | MachineDetails;
};

export const Labels = {
  HardwareInfo: "Hardware Information",
  System: "System",
  SysVendor: "Vendor",
  SysProduct: "Product",
  SysVersion: "Version",
  Serial: "Serial",
  Unknown: "Unknown",
  Mainboard: "Mainboard",
  MainboardVendor: "Vendor",
  MainboardProduct: "Product",
  MainboardFirmware: "Firmware",
  BiosBootMode: "Boot mode",
  MainboardVersion: "Version",
  Date: "Date",
} as const;

const HardwareCard = ({ node }: Props): React.ReactElement => {
  return (
    <Card aria-label={Labels.HardwareInfo} className="hardware-card">
      <div className="u-sv1 p-muted-heading">{Labels.HardwareInfo}</div>
      <span>{Labels.System}</span>
      <LabelledList
        aria-label={Labels.System}
        className="hardware-card__section p-list--divided"
        items={[
          {
            label: Labels.SysVendor,
            value: node.metadata.system_vendor || Labels.Unknown,
          },
          {
            label: Labels.SysProduct,
            value: node.metadata.system_product || Labels.Unknown,
          },
          {
            label: Labels.SysVersion,
            value: node.metadata.system_version || Labels.Unknown,
          },
          {
            label: Labels.Serial,
            value: node.metadata.system_serial || Labels.Unknown,
          },
        ]}
      />
      <span>{Labels.Mainboard}</span>
      <LabelledList
        aria-label={Labels.Mainboard}
        className="hardware-card__section u-no-margin--bottom p-list--divided"
        items={[
          {
            label: Labels.MainboardVendor,
            value: node.metadata.mainboard_vendor || Labels.Unknown,
          },
          {
            label: Labels.MainboardProduct,
            value: node.metadata.mainboard_product || Labels.Unknown,
          },
          {
            label: Labels.MainboardFirmware,
            value: node.metadata.mainboard_firmware_vendor || Labels.Unknown,
          },
          {
            label: Labels.BiosBootMode,
            value: node.bios_boot_method
              ? node.bios_boot_method.toUpperCase()
              : Labels.Unknown,
          },
          {
            label: Labels.MainboardVersion,
            value: node.metadata.mainboard_firmware_version || Labels.Unknown,
          },
          {
            label: Labels.Date,
            value: node.metadata.mainboard_firmware_date || Labels.Unknown,
          },
        ]}
      />
    </Card>
  );
};

export default HardwareCard;
