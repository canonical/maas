import type { ReactElement } from "react";
import { useCallback } from "react";

import { Col, Row, Spinner, Textarea } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import VLANControllers from "../VLANControllers";

import FabricSelect from "@/app/base/components/FabricSelect";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import SpaceSelect from "@/app/base/components/SpaceSelect";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { RootState } from "@/app/store/root/types";
import { getSpaceDisplay } from "@/app/store/space/utils";
import { VLANMTURange, VLANVidRange } from "@/app/store/types/enum";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import type { VLAN } from "@/app/store/vlan/types";
import { VLANMeta } from "@/app/store/vlan/types";
import { isId } from "@/app/utils";

type EditVLANProps = {
  id: VLAN[VLANMeta.PK];
};

export type FormValues = {
  description: VLAN["description"];
  fabric: VLAN["fabric"];
  mtu: VLAN["mtu"];
  name: VLAN["name"];
  space?: VLAN["space"];
  vid: VLAN["vid"];
};

const mtuHelp = `MTU must be between ${VLANMTURange.Min} and ${VLANMTURange.Max}`;
const vidHelp = `Vid must be between ${VLANVidRange.Min} and ${VLANVidRange.Max}`;

const Schema = Yup.object().shape({
  description: Yup.string(),
  fabric: Yup.number().required("Fabric is required"),
  mtu: Yup.number()
    .min(VLANMTURange.Min, mtuHelp)
    .max(VLANMTURange.Max, mtuHelp),
  name: Yup.string().nullable(),
  space: Yup.number(),
  vid: Yup.number()
    .min(VLANVidRange.Min, vidHelp)
    .max(VLANVidRange.Max, vidHelp)
    .required("VID is required"),
});

const EditVLAN = ({ id }: EditVLANProps): ReactElement | null => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const vlan = useSelector((state: RootState) =>
    vlanSelectors.getById(state, id)
  );
  const saved = useSelector(vlanSelectors.saved);
  const saving = useSelector(vlanSelectors.saving);
  const errors = useSelector(vlanSelectors.errors);
  const cleanup = useCallback(() => vlanActions.cleanup(), []);

  if (!vlan) {
    return (
      <span data-testid="Spinner">
        <Spinner text="Loading..." />
      </span>
    );
  }
  const initialValues = {
    description: vlan.description,
    fabric: vlan.fabric,
    mtu: vlan.mtu,
    name: vlan.name,
    vid: vlan.vid,
    space: isId(vlan.space) ? vlan.space : undefined,
  };

  return (
    <FormikForm<FormValues>
      aria-label="Edit VLAN"
      cleanup={cleanup}
      errors={errors}
      initialValues={initialValues}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Save VLAN",
        category: "VLAN details",
        label: "Edit VLAN form",
      }}
      onSubmit={(values) => {
        // Clear the errors from the previous submission.
        dispatch(cleanup());
        dispatch(
          vlanActions.update({
            [VLANMeta.PK]: vlan[VLANMeta.PK],
            ...values,
          })
        );
      }}
      onSuccess={closeSidePanel}
      resetOnSave
      saved={saved}
      saving={saving}
      submitLabel="Save summary"
      validationSchema={Schema}
    >
      <Row>
        <Col size={12}>
          <FormikField label="VID" name="vid" required type="text" />
          <FormikField label="Name" name="name" type="text" />
          <FormikField label="MTU" name="mtu" type="text" />
          <FormikField
            component={Textarea}
            label="Description"
            name="description"
          />
        </Col>
        <Col size={12}>
          <SpaceSelect
            defaultOption={{ label: getSpaceDisplay(null), value: "" }}
            name="space"
          />
          <FabricSelect defaultOption={null} name="fabric" />
          <VLANControllers id={id} />
        </Col>
      </Row>
    </FormikForm>
  );
};

export default EditVLAN;
