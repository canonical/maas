import { Tabs } from "@canonical/react-components";
import { Route, useLocation, Link, Routes } from "react-router";

import DownloadMenu from "./DownloadMenu";
import EventLogs from "./EventLogs";
import InstallationOutput from "./InstallationOutput";

import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import type { Node } from "@/app/store/types/node";
import { getRelativeRoute } from "@/app/utils";

type GenerateURL = (
  args: { id: Node["system_id"] } | null,
  unmodified?: boolean
) => string;

type Props = {
  node: ControllerDetails | MachineDetails;
  urls: {
    events: GenerateURL;
    index: GenerateURL;
    installationOutput: GenerateURL;
  };
};

const NodeLogs = ({ node, urls }: Props): React.ReactElement => {
  const { pathname } = useLocation();

  const showingOutput = pathname.startsWith(
    urls.installationOutput({ id: node.system_id })
  );

  return (
    <>
      <div className="u-position--relative">
        <Tabs
          links={[
            {
              active:
                pathname.startsWith(urls.events({ id: node.system_id })) ||
                !showingOutput,
              component: Link,
              label: "Event log",
              to: urls.events({ id: node.system_id }),
            },
            {
              active: showingOutput,
              component: Link,
              label: "Installation output",
              to: urls.installationOutput({ id: node.system_id }),
            },
          ]}
        />
        <DownloadMenu node={node} />
      </div>
      <Routes>
        <Route
          element={<InstallationOutput node={node} />}
          path={getRelativeRoute(
            urls.installationOutput(null),
            urls.index(null)
          )}
        />
        {[urls.index(null), urls.events(null)].map((path) => (
          <Route
            element={<EventLogs node={node} />}
            key={path}
            path={getRelativeRoute(path, urls.index(null))}
          />
        ))}
      </Routes>
    </>
  );
};

export default NodeLogs;
