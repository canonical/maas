import type { ChangeEvent } from "react";

import { Col, Row } from "@canonical/react-components";
import { useFormikContext } from "formik";

import type { SetPoolFormValues } from "../types";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import ResourcePoolSelect from "@/app/base/components/ResourcePoolSelect";

export const SetPoolFormFields = (): React.ReactElement => {
  const { handleChange, values, setFieldValue, setFieldTouched } =
    useFormikContext<SetPoolFormValues>();

  const handleRadioChange = (evt: ChangeEvent<HTMLInputElement>) => {
    handleChange(evt);
    // Reset the name field when changing the radio options otherwise the
    // selected/provided name will appear in the different name inputs.
    setFieldValue("name", "").catch((reason: unknown) => {
      throw new FormikFieldChangeError(
        "name",
        "setFieldValue",
        reason as string
      );
    });
    setFieldTouched("name", false, false).catch((reason: unknown) => {
      throw new FormikFieldChangeError(
        "name",
        "setFieldTouched",
        reason as string
      );
    });
  };

  return (
    <Row>
      <Col size={12}>
        <ul className="p-inline-list u-equal-height u-no-margin--bottom">
          <li className="p-inline-list__item">
            <FormikField
              data-testid="select-pool"
              label="Select pool"
              name="poolSelection"
              onChange={handleRadioChange}
              type="radio"
              value="select"
            />
          </li>
          <li className="p-inline-list__item">
            <FormikField
              data-testid="create-pool"
              label="Create pool"
              name="poolSelection"
              onChange={handleRadioChange}
              type="radio"
              value="create"
            />
          </li>
        </ul>
        {values.poolSelection === "select" ? (
          <ResourcePoolSelect name="name" required />
        ) : (
          <>
            <FormikField label="Name" name="name" required type="text" />
            <FormikField label="Description" name="description" type="text" />
          </>
        )}
      </Col>
    </Row>
  );
};

export default SetPoolFormFields;
