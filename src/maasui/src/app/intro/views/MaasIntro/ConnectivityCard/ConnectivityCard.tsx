import { Col, Row } from "@canonical/react-components";
import { useFormikContext } from "formik";

import type { MaasIntroValues } from "../types";

import FormikField from "@/app/base/components/FormikField";
import IntroCard from "@/app/intro/components/IntroCard";

export enum Labels {
  UpstreamDns = "DNS forwarder",
  MainArchiveUrl = "Ubuntu archive",
  PortsArchiveUrl = "Ubuntu extra architectures",
  HttpProxy = "APT \u0026 HTTP/HTTPS proxy server",
}

const ConnectivityCard = (): React.ReactElement => {
  const { errors } = useFormikContext<MaasIntroValues>();
  const showErrorIcon =
    errors.httpProxy ||
    errors.mainArchiveUrl ||
    errors.portsArchiveUrl ||
    errors.upstreamDns;

  return (
    <IntroCard
      complete={!showErrorIcon}
      data-testid="maas-connectivity-form"
      hasErrors={!!showErrorIcon}
      title="Connectivity"
    >
      <Row>
        <Col size={6}>
          <FormikField
            help="A space-separated list of upstream DNS servers to which MAAS should forward requests for domains not managed by MAAS directly."
            label={Labels.UpstreamDns}
            name="upstreamDns"
            placeholder="e.g: 8.8.8.8 8.8.4.4"
            type="text"
          />
          <FormikField
            help="The server where machines retrieve packages for Intel architectures."
            label={Labels.MainArchiveUrl}
            name="mainArchiveUrl"
            type="text"
          />
          <FormikField
            help="Archive used by machines to retrieve packages for non-Intel architectures."
            label={Labels.PortsArchiveUrl}
            name="portsArchiveUrl"
            type="text"
          />
          <FormikField
            help="This will be passed onto deployed machines to use as a proxy for APT and YUM traffic. MAAS also uses the proxy for downloading boot images. If no URL is provided, the built-in MAAS proxy will be used."
            label={Labels.HttpProxy}
            name="httpProxy"
            type="text"
          />
        </Col>
      </Row>
    </IntroCard>
  );
};

export default ConnectivityCard;
