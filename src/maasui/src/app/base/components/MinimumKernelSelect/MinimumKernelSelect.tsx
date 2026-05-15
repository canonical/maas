import type { HTMLProps } from "react";

import { Select } from "@canonical/react-components";
import { useSelector } from "react-redux";

import FormikField from "@/app/base/components/FormikField";
import { useFetchActions } from "@/app/base/hooks";
import { generalActions } from "@/app/store/general";
import { hweKernels as hweKernelsSelectors } from "@/app/store/general/selectors";

type Props = HTMLProps<HTMLSelectElement> & {
  disabled?: boolean;
  label?: string;
  name: string;
};

export enum Labels {
  DefaultOption = "Select minimum kernel",
  NoneOption = "No minimum kernel",
  Select = "Minimum kernel",
}

export const MinimumKernelSelect = ({
  disabled = false,
  label = Labels.Select,
  name,
  ...props
}: Props): React.ReactElement => {
  const hweKernels = useSelector(hweKernelsSelectors.get);
  const hweKernelsLoaded = useSelector(hweKernelsSelectors.loaded);

  useFetchActions([generalActions.fetchHweKernels]);

  return (
    <FormikField
      component={Select}
      disabled={!hweKernelsLoaded || disabled}
      label={label}
      name={name}
      options={[
        {
          label: Labels.DefaultOption,
          disabled: true,
        },
        { label: Labels.NoneOption, value: "" },
        ...hweKernels.map((kernel) => ({
          key: `kernel-${kernel[1]}`,
          label: kernel[1],
          value: kernel[0],
        })),
      ]}
      {...props}
    />
  );
};

export default MinimumKernelSelect;
