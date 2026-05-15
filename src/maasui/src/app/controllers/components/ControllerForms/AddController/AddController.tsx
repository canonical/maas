import type { ChangeEvent } from "react";
import { useState } from "react";

import { ExternalLink } from "@canonical/maas-react-components";
import { Button, CodeSnippet, Col, Row } from "@canonical/react-components";
import { useSelector } from "react-redux";

import docsUrls from "@/app/base/docsUrls";
import { useSidePanel } from "@/app/base/side-panel-context";
import configSelectors from "@/app/store/config/selectors";
import { version as versionSelectors } from "@/app/store/general/selectors";

export const AddController = (): React.ReactElement => {
  const maasUrl = useSelector(configSelectors.maasUrl);
  const rpcSharedSecret = useSelector(configSelectors.rpcSharedSecret);
  const minorVersion = useSelector(versionSelectors.minor);
  const [variant, setVariant] = useState("Snap");
  const { closeSidePanel } = useSidePanel();

  const variantDropdown = {
    "aria-label": "version",
    value: variant,
    onChange: (e: ChangeEvent<HTMLSelectElement>) => {
      setVariant(e.target.value);
    },
    options: [
      {
        label: `v${minorVersion} Snap`,
        value: "snap",
      },
      {
        label: `v${minorVersion} Packages`,
        value: "packages",
      },
    ],
  };
  const dropdowns = [variantDropdown];

  return (
    <>
      <p>
        To add a new rack controller, SSH into the rack controller and run the
        commands below. Confirm that the MAAS version is the same as the main
        rack controller.
      </p>
      {variant === "packages" ? (
        <CodeSnippet
          blocks={[
            {
              dropdowns,
              code: `sudo apt-add-repository ppa:maas/${minorVersion}`,
            },
            {
              code: "sudo apt install maas-rack-controller",
            },
          ]}
        />
      ) : (
        <CodeSnippet
          blocks={[
            {
              dropdowns,
              code: `sudo snap install maas --channel=${minorVersion}`,
            },
          ]}
        />
      )}
      <p>
        Register the rack controller with this MAAS. If the rack controller (and
        machines) don't have access to the URL, use a different IP address to
        allow connection.
      </p>
      {variant === "packages" ? (
        <CodeSnippet
          blocks={[
            {
              dropdowns,
              code: `sudo maas-rack register --url ${maasUrl} --secret ${rpcSharedSecret}`,
            },
          ]}
          data-testid="register-snippet"
        />
      ) : (
        <CodeSnippet
          blocks={[
            {
              dropdowns,
              code: `sudo maas init rack --maas-url ${maasUrl} --secret ${rpcSharedSecret}`,
            },
          ]}
          data-testid="register-snippet"
        />
      )}
      <Row>
        <Col size={6}>
          <ExternalLink to={docsUrls.rackController}>
            Help with adding a rack controller
          </ExternalLink>
        </Col>
        <Col className="u-align--right" size={6}>
          <Button data-testid="add-controller-close" onClick={closeSidePanel}>
            Close
          </Button>
        </Col>
      </Row>
    </>
  );
};

export default AddController;
