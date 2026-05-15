import { useState } from "react";

import { Button, Col, Row } from "@canonical/react-components";
import { useFormikContext } from "formik";

import type { UpdateCertificateValues } from "../UpdateCertificate";

import CertificateDownload from "@/app/base/components/CertificateDownload";
import CertificateFields from "@/app/base/components/CertificateFields";
import CertificateMetadata from "@/app/base/components/CertificateMetadata";
import FormikField from "@/app/base/components/FormikField";
import type { GeneratedCertificate } from "@/app/store/general/types";

type Props = {
  generatedCertificate: GeneratedCertificate | null;
  shouldGenerateCert: boolean;
  setShouldGenerateCert: (shouldGenerateCert: boolean) => void;
};

const UpdateCertificateFields = ({
  generatedCertificate,
  shouldGenerateCert,
  setShouldGenerateCert,
}: Props): React.ReactElement => {
  const [usePassword, setUsePassword] = useState(false);
  const { resetForm } = useFormikContext<UpdateCertificateValues>();

  return (
    <Row>
      <Col size={6}>
        {generatedCertificate ? (
          <div data-testid="certificate-data">
            <CertificateMetadata
              metadata={{
                CN: generatedCertificate.CN,
                expiration: generatedCertificate.expiration,
                fingerprint: generatedCertificate.fingerprint,
              }}
            />
            <p>Run the command below in the LXD CLI or use trust password:</p>
            <CertificateDownload
              certificate={generatedCertificate.certificate}
              filename={generatedCertificate.CN}
              isGenerated
            />
            <FormikField
              disabled={!usePassword}
              label="Use trust password (not secure!)"
              name="password"
              type="password"
            />
            {!usePassword && (
              <Button
                onClick={() => {
                  setUsePassword(true);
                }}
              >
                Add
              </Button>
            )}
          </div>
        ) : (
          <CertificateFields
            data-testid="authentication-fields"
            onShouldGenerateCert={(shouldGenerateCert) => {
              setShouldGenerateCert(shouldGenerateCert);
              resetForm();
            }}
            shouldGenerateCert={shouldGenerateCert}
          />
        )}
      </Col>
    </Row>
  );
};

export default UpdateCertificateFields;
