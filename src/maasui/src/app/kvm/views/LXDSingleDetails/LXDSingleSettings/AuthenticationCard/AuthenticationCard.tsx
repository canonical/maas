import type { ReactNode } from "react";
import { useState } from "react";

import { Button, Col, Icon, Row, Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import UpdateCertificate from "./UpdateCertificate";

import CertificateDetails from "@/app/base/components/CertificateDetails";
import FormCard from "@/app/base/components/FormCard";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import { isPodDetails } from "@/app/store/pod/utils";
import type { RootState } from "@/app/store/root/types";

type Props = {
  hostId: Pod["id"] | null;
  objectName?: string | null;
};

const AuthenticationCard = ({
  hostId,
  objectName,
}: Props): React.ReactElement => {
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, hostId)
  );
  const [showUpdateCertificate, setShowUpdateCertificate] = useState(false);

  let content: ReactNode = (
    <p>
      <Spinner text="Loading" />
    </p>
  );
  if (isPodDetails(pod)) {
    const { certificate: certificateMetadata, power_parameters } = pod;
    const hasCertificateData = !!(
      certificateMetadata &&
      power_parameters?.certificate &&
      power_parameters.key
    );
    if (showUpdateCertificate || !hasCertificateData) {
      content = (
        <UpdateCertificate
          closeForm={() => {
            setShowUpdateCertificate(false);
          }}
          hasCertificateData={hasCertificateData}
          objectName={objectName}
          pod={pod}
        />
      );
    } else {
      content = (
        <Row>
          <Col size={6}>
            <CertificateDetails
              certificate={power_parameters?.certificate as string}
              eventCategory="KVM configuration"
              metadata={certificateMetadata}
            />
          </Col>
          <hr />
          <div className="u-align--right">
            <Button
              className="u-no-margin--bottom"
              data-testid="show-update-certificate"
              onClick={() => {
                setShowUpdateCertificate(true);
              }}
            >
              <span className="u-nudge-left--small">
                <Icon name="change-version" />
              </span>
              Update certificate
            </Button>
          </div>
        </Row>
      );
    }
  }

  return (
    <FormCard
      className="authentication-card"
      data-testid="authentication-card"
      highlighted={false}
      sidebar={false}
      title="Authentication"
    >
      {content}
    </FormCard>
  );
};

export default AuthenticationCard;
