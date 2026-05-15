import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import DynamicSelect from "@/app/base/components/DynamicSelect";
import type { Props as FormikFieldProps } from "@/app/base/components/FormikField/FormikField";
import { useFetchActions } from "@/app/base/hooks";
import { generalActions } from "@/app/store/general";
import { bondOptions as bondOptionsSelectors } from "@/app/store/general/selectors";

type Props = FormikFieldProps & {
  defaultOption?: Option | null;
};

type Option = { label: string; value: string };

export const BondModeSelect = ({
  defaultOption = { label: "Select bond mode", value: "" },
  name,
  ...props
}: Props): React.ReactElement => {
  const bondModes = useSelector(bondOptionsSelectors.modes);
  const loaded = useSelector(bondOptionsSelectors.loaded);
  const options: Option[] =
    bondModes?.map((mode) => ({
      label: mode,
      value: mode,
    })) || [];

  if (defaultOption) {
    options.unshift(defaultOption);
  }

  useFetchActions([generalActions.fetchBondOptions]);

  if (!loaded) {
    return <Spinner />;
  }

  return (
    <DynamicSelect label="Bond mode" name={name} options={options} {...props} />
  );
};

export default BondModeSelect;
