import DynamicSelect from "@/app/base/components/DynamicSelect";
import type { Props as FormikFieldProps } from "@/app/base/components/FormikField/FormikField";
import type { Subnet } from "@/app/store/subnet/types";
import { NetworkInterfaceTypes, NetworkLinkMode } from "@/app/store/types/enum";
import { LINK_MODE_DISPLAY } from "@/app/store/utils";

type Props = FormikFieldProps & {
  defaultOption?: { label: string; value: string } | null;
  interfaceType: NetworkInterfaceTypes;
  subnet?: Subnet["id"] | null;
};

export enum Label {
  DefaultOption = "Select IP mode",
  Select = "IP assignment",
}

const getAvailableLinkModes = (
  interfaceType: NetworkInterfaceTypes | null,
  subnet?: Subnet["id"] | null
): NetworkLinkMode[] => {
  // If a subnet has not been chosen then the only allowed mode is LINK_UP.
  if (!subnet) {
    return [NetworkLinkMode.LINK_UP];
  }
  const modes = [NetworkLinkMode.AUTO, NetworkLinkMode.STATIC];
  const isAlias = interfaceType === NetworkInterfaceTypes.ALIAS;
  if (!isAlias) {
    modes.push(NetworkLinkMode.LINK_UP);
    // Can't run DHCP twice on one NIC.
    modes.push(NetworkLinkMode.DHCP);
  }
  return modes;
};

export const LinkModeSelect = ({
  defaultOption = { label: Label.DefaultOption, value: "" },
  interfaceType,
  name,
  subnet,
  ...props
}: Props): React.ReactElement => {
  const availableModes = getAvailableLinkModes(interfaceType, subnet);
  const modeOptions = availableModes.map((mode) => ({
    label: LINK_MODE_DISPLAY[mode],
    value: mode.toString(),
  }));

  if (defaultOption) {
    modeOptions.unshift(defaultOption);
  }

  return (
    <DynamicSelect
      label={Label.Select}
      name={name}
      options={modeOptions}
      {...props}
    />
  );
};

export default LinkModeSelect;
