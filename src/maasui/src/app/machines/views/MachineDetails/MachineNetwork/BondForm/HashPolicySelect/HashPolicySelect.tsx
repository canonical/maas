import { Spinner } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import type { BondFormValues } from "../types";

import DynamicSelect from "@/app/base/components/DynamicSelect";
import type { Props as FormikFieldProps } from "@/app/base/components/FormikField/FormikField";
import { useFetchActions } from "@/app/base/hooks";
import { generalActions } from "@/app/store/general";
import { bondOptions as bondOptionsSelectors } from "@/app/store/general/selectors";
import { BondMode, BondXmitHashPolicy } from "@/app/store/general/types";

type Props = FormikFieldProps & {
  bondMode?: BondMode | null;
  defaultOption?: { label: string; value: string } | null;
};

type Option = { label: string; value: string };

const generateCaution = (
  bondMode: Props["bondMode"],
  xmitHashPolicy: BondXmitHashPolicy
) =>
  bondMode === BondMode.LINK_AGGREGATION &&
  [BondXmitHashPolicy.LAYER3_4, BondXmitHashPolicy.ENCAP3_4].includes(
    xmitHashPolicy
  )
    ? "This hash policy is not fully 802.3ad compliant."
    : null;

export const HashPolicySelect = ({
  bondMode,
  defaultOption = { label: "Select XMIT hash policy", value: "" },
  name,
  ...props
}: Props): React.ReactElement => {
  const xmitHashPolicies = useSelector(bondOptionsSelectors.xmitHashPolicies);
  const loaded = useSelector(bondOptionsSelectors.loaded);
  const { values } = useFormikContext<BondFormValues>();
  const options: Option[] =
    xmitHashPolicies?.map((policy) => ({
      label: policy,
      value: policy,
    })) || [];

  if (defaultOption) {
    options.unshift(defaultOption);
  }

  useFetchActions([generalActions.fetchBondOptions]);

  if (!loaded) {
    return <Spinner />;
  }

  return (
    <DynamicSelect
      caution={generateCaution(
        bondMode,
        values[name as keyof BondFormValues] as BondXmitHashPolicy
      )}
      label="Hash policy"
      name={name}
      options={options}
      {...props}
    />
  );
};

export default HashPolicySelect;
