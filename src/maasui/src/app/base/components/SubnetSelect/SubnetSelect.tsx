import type { SelectProps } from "@canonical/react-components";
import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import DynamicSelect from "@/app/base/components/DynamicSelect";
import type { Props as FormikFieldProps } from "@/app/base/components/FormikField/FormikField";
import { useFetchActions } from "@/app/base/hooks";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";
import { getSubnetDisplay } from "@/app/store/subnet/utils";
import { simpleSortByKey } from "@/app/utils";

type Option = NonNullable<SelectProps["options"]>[0];

type Props = FormikFieldProps & {
  defaultOption?: Option | null;
  filterFunction?: (subnet: Subnet) => boolean;
  vlan?: Subnet["vlan"];
};

export enum Label {
  Select = "Subnet",
}

export const SubnetSelect = ({
  defaultOption = { label: "Select subnet", value: "" },
  filterFunction,
  name,
  vlan,
  ...props
}: Props): React.ReactElement => {
  let subnets: Subnet[] = useSelector(subnetSelectors.all);
  const subnetsLoaded = useSelector(subnetSelectors.loaded);

  useFetchActions([subnetActions.fetch]);

  if (!subnetsLoaded) {
    return <Spinner />;
  }

  if (subnets && (vlan || vlan === 0)) {
    subnets = subnets.filter((subnet) => subnet.vlan === vlan);
  }

  if (subnets && filterFunction) {
    subnets = subnets.filter(filterFunction);
  }

  const subnetOptions = subnets
    .map<Option>((subnet) => ({
      label: getSubnetDisplay(subnet),
      value: subnet.id.toString(),
    }))
    .sort(simpleSortByKey("label", { alphanumeric: true }));

  if (defaultOption) {
    subnetOptions.unshift(defaultOption);
  }

  return (
    <DynamicSelect
      label="Subnet"
      name={name}
      options={subnetOptions}
      {...props}
    />
  );
};

export default SubnetSelect;
