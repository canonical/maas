import { Col, Input, Row } from "@canonical/react-components";
import { useFormikContext } from "formik";

import type { AuthenticationFormValues } from "../AuthenticationForm";

import CertificateDownload from "@/app/base/components/CertificateDownload";
import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import type { GeneratedCertificate } from "@/app/store/general/types";

type Props = {
  disabled: boolean;
  generatedCertificate: GeneratedCertificate | null;
  setUseCertificate: (useCert: boolean) => void;
  useCertificate: boolean;
};

export const AuthenticationFormFields = ({
  disabled,
  generatedCertificate,
  setUseCertificate,
  useCertificate,
}: Props): React.ReactElement => {
  const { setFieldTouched, setFieldValue } =
    useFormikContext<AuthenticationFormValues>();

  return (
    <Row>
      <Col size={12}>
        <Input
          checked={useCertificate}
          disabled={disabled}
          id="use-certificate"
          label="Add trust to LXD via command line"
          onChange={() => {
            setUseCertificate(true);
            setFieldTouched("password", false).catch((reason: unknown) => {
              throw new FormikFieldChangeError(
                "password",
                "setFieldTouched",
                reason as string
              );
            });
            setFieldValue("password", "").catch((reason: unknown) => {
              throw new FormikFieldChangeError(
                "password",
                "setFieldValue",
                reason as string
              );
            });
          }}
          type="radio"
        />
        <p>Run the command below in the LXD CLI:</p>
        {generatedCertificate && (
          <CertificateDownload
            certificate={generatedCertificate.certificate}
            filename={generatedCertificate.CN}
            isGenerated
          />
        )}
      </Col>
      <Col size={12}>
        <Input
          checked={!useCertificate}
          disabled={disabled}
          id="use-password"
          label="Use trust password (not secure!)"
          onChange={() => {
            setUseCertificate(false);
          }}
          type="radio"
        />
        <FormikField
          aria-label="Password"
          disabled={disabled || useCertificate}
          name="password"
          type="password"
        />
      </Col>
    </Row>
  );
};

export default AuthenticationFormFields;
