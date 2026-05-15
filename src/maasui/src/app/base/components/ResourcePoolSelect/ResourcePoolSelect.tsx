import type { HTMLProps } from "react";
import React from "react";

import { Select } from "@canonical/react-components";

import { usePools } from "@/app/api/query/pools";
import FormikField from "@/app/base/components/FormikField";

type Props = HTMLProps<HTMLSelectElement> & {
  disabled?: boolean;
  label?: string;
  name: string;
  valueKey?: "id" | "name";
};

export const ResourcePoolSelect = ({
  disabled = false,
  label = "Resource pool",
  name,
  valueKey = "name",
  ...props
}: Props): React.ReactElement => {
  const listPools = usePools();
  const resourcePools = listPools.data?.items || [];

  return (
    <FormikField
      component={Select}
      disabled={!listPools.isSuccess || disabled}
      label={label}
      name={name}
      options={[
        { label: "Select resource pool", value: "", disabled: true },
        ...resourcePools.map((resourcePool) => ({
          key: `resource-pool-${resourcePool.id}`,
          label: resourcePool.name,
          value: resourcePool[valueKey],
        })),
      ]}
      {...props}
    />
  );
};

export default ResourcePoolSelect;
