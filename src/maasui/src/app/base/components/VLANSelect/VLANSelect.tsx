import { useEffect } from "react";

import type { SelectProps } from "@canonical/react-components";
import { Spinner } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useDispatch, useSelector } from "react-redux";

import DynamicSelect from "@/app/base/components/DynamicSelect";
import type { Props as FormikFieldProps } from "@/app/base/components/FormikField/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import fabricSelectors from "@/app/store/fabric/selectors";
import type { RootState } from "@/app/store/root/types";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import { VlanVid } from "@/app/store/vlan/types";
import type { VLAN } from "@/app/store/vlan/types";
import { getVLANDisplay } from "@/app/store/vlan/utils";
import { isId } from "@/app/utils";

type Option = NonNullable<SelectProps["options"]>[0];

type Props = FormikFieldProps & {
  defaultOption?: Option | null;
  fabric?: VLAN["fabric"];
  generateName?: (vlan: VLAN) => string;
  includeDefaultVlan?: boolean;
  showSpinnerOnLoad?: boolean;
  setDefaultValueFromFabric?: boolean;
  vlans?: VLAN[] | null;
};

export enum Label {
  Select = "VLAN",
}

export const VLANSelect = ({
  defaultOption = { disabled: true, label: "Select VLAN", value: "" },
  fabric,
  generateName,
  includeDefaultVlan = true,
  showSpinnerOnLoad = false,
  setDefaultValueFromFabric,
  name,
  vlans,
  disabled,
  ...props
}: Props): React.ReactElement => {
  const dispatch = useDispatch();
  let vlanList: VLAN[] = useSelector(vlanSelectors.all);
  const vlansLoaded = useSelector(vlanSelectors.loaded);
  const selectedFabric = useSelector((state: RootState) =>
    fabricSelectors.getById(state, fabric)
  );
  const { setFieldValue } = useFormikContext();

  const generateVLANName = (vlan: VLAN) =>
    generateName ? generateName(vlan) : getVLANDisplay(vlan) || "";

  const sort = (a: VLAN, b: VLAN): number => {
    // Put the untagged vlan(s) at the start.
    if (a.vid === VlanVid.UNTAGGED && b.vid === VlanVid.UNTAGGED) {
      return 0;
    } else if (a.vid === VlanVid.UNTAGGED) {
      return -1;
    } else if (b.vid === VlanVid.UNTAGGED) {
      return 1;
    }
    return (
      getVLANDisplay(a)?.localeCompare(generateVLANName(b), "en", {
        numeric: true,
      }) || 0
    );
  };

  useEffect(() => {
    if (setDefaultValueFromFabric) {
      const vlan = selectedFabric?.default_vlan_id;
      if (isId(vlan)) {
        setFieldValue("vlan", vlan).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            "vlan",
            "setFieldValue",
            reason as string
          );
        });
      }
    }
  }, [setDefaultValueFromFabric, setFieldValue, selectedFabric]);

  useEffect(() => {
    if (!vlansLoaded) dispatch(vlanActions.fetch());
  }, [vlansLoaded, dispatch]);

  if (showSpinnerOnLoad && !vlansLoaded) {
    return <Spinner />;
  }

  if (vlans) {
    vlanList = vlans;
  } else if (vlanList && (fabric || fabric === 0)) {
    vlanList = vlanList.filter((vlan) => vlan.fabric === fabric);
  }
  if (!includeDefaultVlan) {
    vlanList = vlanList.filter(({ vid }) => vid !== VlanVid.UNTAGGED);
  }

  const vlanOptions = [...vlanList].sort(sort).map<Option>((vlan) => ({
    label: generateVLANName(vlan),
    value: vlan.id.toString(),
  }));

  if (defaultOption) {
    vlanOptions.unshift(defaultOption);
  }

  return (
    <DynamicSelect
      disabled={!vlansLoaded || disabled}
      label="VLAN"
      name={name}
      options={vlanOptions}
      {...props}
    />
  );
};

export default VLANSelect;
