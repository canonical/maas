import { Select } from "@canonical/react-components";
import { useSelector } from "react-redux";

import FormikField from "@/app/base/components/FormikField";
import type { Props as FormikFieldProps } from "@/app/base/components/FormikField/FormikField";
import { useFetchActions } from "@/app/base/hooks";
import { spaceActions } from "@/app/store/space";
import spaceSelectors from "@/app/store/space/selectors";
import { simpleSortByKey } from "@/app/utils";

type Props = FormikFieldProps & {
  defaultOption?: { label: string; value: string; disabled?: boolean } | null;
};

export const SpaceSelect = ({
  defaultOption = { label: "Select space", value: "", disabled: true },
  name,
  label = "Space",
  disabled,
  ...props
}: Props): React.ReactElement => {
  const spaces = useSelector(spaceSelectors.all);
  const spacesLoaded = useSelector(spaceSelectors.loaded);

  useFetchActions([spaceActions.fetch]);

  return (
    <FormikField
      component={Select}
      disabled={!spacesLoaded || disabled}
      label={label}
      name={name}
      options={[
        ...(defaultOption ? [defaultOption] : []),
        ...spaces
          .map((space) => ({
            label: space.name,
            value: space.id.toString(),
          }))
          .sort(simpleSortByKey("label", { alphanumeric: true })),
      ]}
      {...props}
    />
  );
};

export default SpaceSelect;
