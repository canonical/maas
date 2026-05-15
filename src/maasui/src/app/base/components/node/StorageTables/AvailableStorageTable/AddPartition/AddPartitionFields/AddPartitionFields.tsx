import { Col, Input, Row, Select } from "@canonical/react-components";
import { useFormikContext } from "formik";

import FilesystemFields from "../../FilesystemFields";
import type { AddPartitionValues } from "../AddPartition";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import type { Machine } from "@/app/store/machine/types";

type Props = {
  partitionName: string;
  systemId: Machine["system_id"];
};

export const AddPartitionFields = ({
  partitionName,
  systemId,
}: Props): React.ReactElement => {
  const { handleChange, setFieldTouched, setFieldValue } =
    useFormikContext<AddPartitionValues>();

  return (
    <Row>
      <Col size={12}>
        <Input
          aria-label="Name"
          disabled
          label="Name"
          type="text"
          value={partitionName}
        />
        <Input
          aria-label="Type"
          disabled
          label="Type"
          type="text"
          value="Partition"
        />
        <FormikField
          label="Size"
          min="0"
          name="partitionSize"
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            const value =
              e.target.value !== "" ? parseFloat(e.target.value) : "";
            handleChange(e);
            setFieldValue("partitionSize", value).catch((reason: unknown) => {
              throw new FormikFieldChangeError(
                "partitionSize",
                "setFieldValue",
                reason as string
              );
            });
            setFieldTouched("partitionSize", true, false).catch(
              (reason: unknown) => {
                throw new FormikFieldChangeError(
                  "partitionSize",
                  "setFieldTouched",
                  reason as string
                );
              }
            );
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
              label: "Select partition size unit",
              value: "",
              disabled: true,
            },
            { label: "MB", value: "MB" },
            { label: "GB", value: "GB" },
            { label: "TB", value: "TB" },
          ]}
        />
      </Col>
      <Col size={12}>
        <FilesystemFields systemId={systemId} />
      </Col>
    </Row>
  );
};

export default AddPartitionFields;
