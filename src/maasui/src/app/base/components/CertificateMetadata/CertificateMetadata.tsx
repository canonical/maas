import { Card } from "@canonical/react-components";

import LabelledList from "@/app/base/components/LabelledList";
import type { CertificateMetadata as CertificateMetadataType } from "@/app/store/general/types";

type Props = {
  metadata: CertificateMetadataType;
};

const CertificateMetadata = ({ metadata }: Props): React.ReactElement => {
  return (
    <Card className="certificate-metadata">
      <LabelledList
        className="certificate-metadata__list u-no-margin--bottom"
        items={[
          { label: "CN", value: metadata.CN },
          {
            label: "Expiration date",
            value: metadata.expiration,
          },
          {
            label: "Fingerprint",
            value: metadata.fingerprint,
          },
        ]}
      />
    </Card>
  );
};

export default CertificateMetadata;
