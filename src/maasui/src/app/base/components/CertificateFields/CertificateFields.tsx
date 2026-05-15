import { Input } from "@canonical/react-components";

import UploadTextArea from "@/app/base/components/UploadTextArea";

type Props = {
  certificateFieldName?: string;
  onShouldGenerateCert: (shouldGenerateCert: boolean) => void;
  privateKeyFieldName?: string;
  shouldGenerateCert: boolean;
};

export enum Labels {
  Generate = "Generate new certificate",
  Provide = "Provide certificate and private key",
  UploadCert = "Upload certificate",
  UploadKey = "Upload private key",
}

export const CertificateFields = ({
  certificateFieldName = "certificate",
  onShouldGenerateCert,
  privateKeyFieldName = "key",
  shouldGenerateCert,
}: Props): React.ReactElement => {
  return (
    <>
      <p>Certificate</p>
      <Input
        checked={shouldGenerateCert}
        id="generate-certificate"
        label={Labels.Generate}
        onChange={() => {
          onShouldGenerateCert(true);
        }}
        type="radio"
      />
      <Input
        checked={!shouldGenerateCert}
        id="provide-certificate"
        label={Labels.Provide}
        onChange={() => {
          onShouldGenerateCert(false);
        }}
        type="radio"
        wrapperClassName="u-sv2"
      />
      {!shouldGenerateCert && (
        <>
          <UploadTextArea
            label={Labels.UploadCert}
            name={certificateFieldName}
            placeholder="Paste or upload a certificate."
            rows={5}
          />
          <UploadTextArea
            label={Labels.UploadKey}
            name={privateKeyFieldName}
            placeholder="Paste or upload a private key."
            rows={5}
          />
        </>
      )}
    </>
  );
};

export default CertificateFields;
