import { ExternalLink } from "@canonical/maas-react-components";

import CertificateDownload from "@/app/base/components/CertificateDownload";
import CertificateMetadata from "@/app/base/components/CertificateMetadata";
import { useSendAnalytics } from "@/app/base/hooks";
import type {
  CertificateData,
  CertificateMetadata as CertificateMetadataType,
} from "@/app/store/general/types";

type Props = {
  certificate: CertificateData["certificate"];
  eventCategory: string;
  metadata: CertificateMetadataType;
};

export enum Labels {
  ReadMore = "Read more about authentication",
}

const CertificateDetails = ({
  certificate,
  eventCategory,
  metadata,
}: Props): React.ReactElement => {
  const sendAnalytics = useSendAnalytics();

  return (
    <div className="certificate-details">
      <p>Certificate</p>
      <p>
        <ExternalLink
          data-testid="read-more-link"
          onClick={() => {
            sendAnalytics(
              eventCategory,
              "Click link to LXD authentication discourse",
              "Read more about authentication"
            );
          }}
          to="https://discourse.maas.io/t/lxd-authentication/4856"
        >
          {Labels.ReadMore}
        </ExternalLink>
      </p>
      <CertificateMetadata metadata={metadata} />
      <CertificateDownload certificate={certificate} filename={metadata.CN} />
    </div>
  );
};

export default CertificateDetails;
