import type { ChangeEvent, ReactElement } from "react";
import { useState } from "react";

import { ExternalLink } from "@canonical/maas-react-components";
import { Button, CodeSnippet } from "@canonical/react-components";

import { useGenerateToken } from "@/app/api/query/racks";
import CopyButton from "@/app/base/components/CopyButton";
import docsUrls from "@/app/base/docsUrls";
import { useSidePanel } from "@/app/base/side-panel-context";
import "./_index.scss";

type GuidedProvisioningProps = {
  id: number;
};

const GuidedProvisioning = ({ id }: GuidedProvisioningProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();

  const [maasVersion, setMaasVersion] = useState("3.7");
  const generateTokenMutation = useGenerateToken();
  return (
    <div>
      To register a controller to the rack using guided provisioning, SSH into
      the controller and run the commands below.
      <CodeSnippet
        blocks={[
          {
            code: "sudo snap install maas-agent --channel=3.7",
            dropdowns: [
              {
                options: [{ label: "v3.7 Snap", value: "3.7" }],
                value: maasVersion,
                onChange: (e: ChangeEvent<HTMLSelectElement>) => {
                  setMaasVersion(e.target.value);
                },
              },
            ],
          },
        ]}
        className="u-nudge-down"
        data-testid="first-command-snippet"
      />
      Generate a bootstrap token and use it to initialize the MAAS agent.
      <CodeSnippet
        blocks={[
          {
            code: "maas-agent init --token <TOKEN> ",
            dropdowns: [
              {
                options: [{ label: "v3.7 Snap", value: "3.7" }],
                value: maasVersion,
                onChange: (e: ChangeEvent<HTMLSelectElement>) => {
                  setMaasVersion(e.target.value);
                },
              },
            ],
          },
        ]}
        className="u-nudge-down"
        data-testid="second-command-snippet"
      />
      {generateTokenMutation.isSuccess ? (
        <CodeSnippet
          blocks={[
            {
              code: (
                <span>
                  <span className="u-flex--end u-margin-bottom--medium">
                    <CopyButton value={generateTokenMutation.data.token} />
                  </span>
                  {generateTokenMutation.data.token}
                </span>
              ),
            },
          ]}
          className="p-agent-token"
        />
      ) : (
        <span className="u-flex--end">
          <Button
            onClick={() => {
              generateTokenMutation.mutate({ path: { rack_id: id } });
            }}
          >
            Generate token
          </Button>
        </span>
      )}
      <hr />
      <span className="u-flex--row u-flex--between">
        <p>
          <ExternalLink to={docsUrls.rackController}>
            Help with registering controllers
          </ExternalLink>
        </p>
        <Button
          onClick={() => {
            closeSidePanel();
          }}
        >
          Close
        </Button>
      </span>
    </div>
  );
};

export default GuidedProvisioning;
