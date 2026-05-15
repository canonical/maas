import { Col, Input, Row, Select } from "@canonical/react-components";
import { useFormikContext } from "formik";

import FilesystemFields from "../../FilesystemFields";
import type { AddLogicalVolumeValues } from "../AddLogicalVolume";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import TagNameField from "@/app/base/components/TagNameField";
import type { Machine } from "@/app/store/machine/types";

type Props = {
  systemId: Machine["system_id"];
};

export const AddLogicalVolumeFields = ({
  systemId,
}: Props): React.ReactElement => {
  const { handleChange, setFieldTouched, setFieldValue } =
    useFormikContext<AddLogicalVolumeValues>();

  return (
    <Row>
      <Col size={12}>
        <FormikField label="Name" name="name" required type="text" />
        <Input disabled label="Type" type="text" value="Logical volume" />
        <FormikField
          label="Size"
          min="0"
          name="size"
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            const value =
              e.target.value !== "" ? parseFloat(e.target.value) : "";
            handleChange(e);
            setFieldValue("size", value).catch((reason: unknown) => {
              throw new FormikFieldChangeError(
                "size",
                "setFieldValue",
                reason as string
              );
            });
            setFieldTouched("size", true, false).catch((reason: unknown) => {
              throw new FormikFieldChangeError(
                "size",
                "setFieldTouched",
                reason as string
              );
            });
          }}
          required
          step="any"
          type="number"
        />
        <FormikField
          component={Select}
          label="Unit"
          name="unit"
          options={[
            {
              label: "Select volume size unit",
              value: "",
              disabled: true,
            },
            { label: "MB", value: "MB" },
            { label: "GB", value: "GB" },
            { label: "TB", value: "TB" },
          ]}
        />
        <TagNameField />
      </Col>
      <Col size={12}>
        <FilesystemFields systemId={systemId} />
      </Col>
    </Row>
  );
};

export default AddLogicalVolumeFields;
