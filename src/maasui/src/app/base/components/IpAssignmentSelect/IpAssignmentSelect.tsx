import { Select } from "@canonical/react-components";

import FormikField from "@/app/base/components/FormikField";
import type { Props as FormikFieldProps } from "@/app/base/components/FormikField/FormikField";
import { DeviceIpAssignment } from "@/app/store/device/types";
import { getIpAssignmentDisplay } from "@/app/store/device/utils";

type Props = Omit<FormikFieldProps<typeof Select>, "component" | "options"> & {
  includeStatic?: boolean;
};

export enum Labels {
  DefaultOption = "Select IP assignment",
  Select = "IP assignment",
}

export const IpAssignmentSelect = ({
  includeStatic = true,
  label = Labels.Select,
  ...props
}: Props): React.ReactElement => {
  return (
    <FormikField
      component={Select}
      help="To manage static DHCP leases for a device, go to the address reservation tab of a subnet."
      label={label}
      options={[
        { label: Labels.DefaultOption, value: "", disabled: true },
        {
          label: getIpAssignmentDisplay(DeviceIpAssignment.DYNAMIC),
          value: DeviceIpAssignment.DYNAMIC,
        },
        ...(includeStatic
          ? [
              {
                label: getIpAssignmentDisplay(DeviceIpAssignment.STATIC),
                value: DeviceIpAssignment.STATIC,
              },
            ]
          : []),
        {
          label: getIpAssignmentDisplay(DeviceIpAssignment.EXTERNAL),
          value: DeviceIpAssignment.EXTERNAL,
        },
      ]}
      {...props}
    />
  );
};

export default IpAssignmentSelect;
