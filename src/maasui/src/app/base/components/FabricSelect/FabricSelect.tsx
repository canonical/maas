import { useEffect } from "react";

import { useDispatch, useSelector } from "react-redux";

import DynamicSelect from "@/app/base/components/DynamicSelect";
import type { Props as FormikFieldProps } from "@/app/base/components/FormikField/FormikField";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import { simpleSortByKey } from "@/app/utils";

type Props = FormikFieldProps & {
  defaultOption?: { label: string; value: string; disabled?: boolean } | null;
};

export enum Label {
  DefaultOption = "Select fabric",
  Select = "Fabric",
}

export const FabricSelect = ({
  defaultOption = { label: Label.DefaultOption, value: "", disabled: true },
  name,
  label = Label.Select,
  disabled,
  ...props
}: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const fabrics = useSelector(fabricSelectors.all);
  const fabricsLoaded = useSelector(fabricSelectors.loaded);

  useEffect(() => {
    if (!fabricsLoaded) dispatch(fabricActions.fetch());
  }, [dispatch, fabricsLoaded]);

  return (
    <DynamicSelect
      disabled={!fabricsLoaded || disabled}
      label={label}
      name={name}
      options={[
        ...(defaultOption ? [defaultOption] : []),
        ...fabrics
          .map((fabric) => ({
            label: fabric.name,
            value: fabric.id.toString(),
          }))
          .sort(simpleSortByKey("label", { alphanumeric: true })),
      ]}
      {...props}
    />
  );
};

export default FabricSelect;
