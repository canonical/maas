import { Tabs } from "@canonical/react-components";
import { Link, Route, Routes, useLocation } from "react-router";

import ScriptStatus from "../../ScriptStatus";
import NodeTestDetails from "../NodeTestDetails/NodeTestDetails";

import MachineCommissioning from "@/app/machines/views/MachineDetails/MachineCommissioning";
import MachineDeployment from "@/app/machines/views/MachineDetails/MachineDeployment";
import MachineTests from "@/app/machines/views/MachineDetails/MachineTests";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import type { Node } from "@/app/store/types/node";
import { getRelativeRoute } from "@/app/utils";

type GenerateURL = (
  args: { id: Node["system_id"] } | null,
  unmodified?: boolean
) => string;

type ScriptResultURL = (
  args: { id: string; scriptResultId: number } | null,
  unmodified?: boolean
) => string;

type Props = {
  node: ControllerDetails | MachineDetails;
  urls: {
    index: GenerateURL;
    commissioning: {
      index: GenerateURL;
      scriptResult: ScriptResultURL;
    };
    testing: {
      index: GenerateURL;
      scriptResult: ScriptResultURL;
    };
    deployment?: {
      index: GenerateURL;
      scriptResult: ScriptResultURL;
    };
  };
};

const NodeScripts = ({ node, urls }: Props) => {
  const { pathname } = useLocation();

  const commissioningPath = urls.commissioning.index({ id: node.system_id });
  const testingPath = urls.testing.index({ id: node.system_id });
  const deploymentPath = urls.deployment?.index({ id: node.system_id }) ?? "";

  const showingCommissioning = pathname.startsWith(commissioningPath);
  const showingTesting = pathname.startsWith(testingPath);
  const showDeployment = pathname.startsWith(deploymentPath);

  return (
    <>
      <Tabs
        links={[
          {
            active:
              showingCommissioning ||
              (!showingCommissioning && !showingTesting && !showDeployment),
            component: Link,
            label: (
              <ScriptStatus status={node.commissioning_status.status}>
                Commissioning
              </ScriptStatus>
            ),
            to: commissioningPath,
          },
          {
            active: showingTesting,
            component: Link,
            label: "Tests",
            to: testingPath,
          },
          ...(deploymentPath
            ? [
                {
                  active: showDeployment,
                  component: Link,
                  label: "Deployment",
                  to: deploymentPath,
                },
              ]
            : []),
        ]}
      />
      <Routes>
        {[urls.index(null), urls.commissioning.index(null)].map((path) => (
          <Route
            element={<MachineCommissioning />}
            key={path}
            path={getRelativeRoute(path, urls.index(null))}
          />
        ))}
        <Route
          element={
            <NodeTestDetails
              getReturnPath={(id) => urls.commissioning.index({ id })}
            />
          }
          path={getRelativeRoute(
            urls.commissioning.scriptResult(null),
            urls.index(null)
          )}
        />
        <Route
          element={<MachineTests />}
          path={getRelativeRoute(urls.testing.index(null), urls.index(null))}
        />
        <Route
          element={
            <NodeTestDetails
              getReturnPath={(id) => urls.testing.index({ id })}
            />
          }
          path={getRelativeRoute(
            urls.testing.scriptResult(null),
            urls.index(null)
          )}
        />
        {"deployment" in urls &&
        urls.deployment &&
        urls.deployment !== undefined ? (
          <>
            <Route
              element={<MachineDeployment />}
              path={getRelativeRoute(
                urls.deployment.index(null),
                urls.index(null)
              )}
            />
            <Route
              element={
                <NodeTestDetails
                  // TS keeps complaining about deployment possibly being undefined,
                  // despite the check above this ensuring it is defined
                  getReturnPath={(id) => urls.deployment!.index({ id })}
                />
              }
              path={getRelativeRoute(
                urls.deployment.scriptResult(null),
                urls.index(null)
              )}
            />
          </>
        ) : null}
      </Routes>
    </>
  );
};

export default NodeScripts;
