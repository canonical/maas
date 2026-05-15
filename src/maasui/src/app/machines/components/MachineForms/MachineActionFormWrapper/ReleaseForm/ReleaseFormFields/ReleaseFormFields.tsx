import { Col, Row } from "@canonical/react-components";
import { useFormikContext } from "formik";

import type { ReleaseFormValues } from "../ReleaseForm";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";

export const ReleaseFormFields = (): React.ReactElement => {
  const { handleChange, setFieldValue, values } =
    useFormikContext<ReleaseFormValues>();

  return (
    <Row>
      <Col size={12}>
        <FormikField
          label="Erase disks before releasing"
          name="enableErase"
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            handleChange(e);
            if (!e.target.checked) {
              setFieldValue("quickErase", false).catch((reason: unknown) => {
                throw new FormikFieldChangeError(
                  "quickErase",
                  "setFieldValue",
                  reason as string
                );
              });
              setFieldValue("secureErase", false).catch((reason: unknown) => {
                throw new FormikFieldChangeError(
                  "secureErase",
                  "setFieldValue",
                  reason as string
                );
              });
            }
          }}
          type="checkbox"
        />
        <FormikField
          disabled={!values.enableErase}
          label="Use secure erase"
          name="secureErase"
          type="checkbox"
        />
        <FormikField
          disabled={!values.enableErase}
          label="Use quick erase (not secure)"
          name="quickErase"
          type="checkbox"
        />
      </Col>
    </Row>
  );
};

export default ReleaseFormFields;
