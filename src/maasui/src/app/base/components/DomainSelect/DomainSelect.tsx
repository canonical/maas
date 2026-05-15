import { Select } from "@canonical/react-components";
import { useSelector } from "react-redux";

import FormikField from "@/app/base/components/FormikField";
import type { Props as FormikFieldProps } from "@/app/base/components/FormikField/FormikField";
import { useFetchActions } from "@/app/base/hooks";
import { domainActions } from "@/app/store/domain";
import domainSelectors from "@/app/store/domain/selectors";

type Props = FormikFieldProps & {
  disabled?: boolean;
  label?: string | null;
  name: string;
  valueKey?: "id" | "name";
};

export enum Labels {
  DefaultLabel = "Domain",
}

export const DomainSelect = ({
  disabled = false,
  label = Labels.DefaultLabel,
  name,
  valueKey = "name",
  ...props
}: Props): React.ReactElement => {
  const domains = useSelector(domainSelectors.all);
  const domainsLoaded = useSelector(domainSelectors.loaded);

  useFetchActions([domainActions.fetch]);

  return (
    <FormikField
      component={Select}
      disabled={!domainsLoaded || disabled}
      label={label}
      name={name}
      options={[
        { label: "Select domain", value: "", disabled: true },
        ...domains.map((domain) => ({
          key: `domain-${domain.id}`,
          label: domain.name,
          value: domain[valueKey],
        })),
      ]}
      {...props}
    />
  );
};

export default DomainSelect;
