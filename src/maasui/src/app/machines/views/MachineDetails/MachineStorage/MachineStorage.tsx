import { ExternalLink } from "@canonical/maas-react-components";
import { Spinner, Strip } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import ChangeStorageLayoutMenu from "./ChangeStorageLayoutMenu";

import StorageTables from "@/app/base/components/node/StorageTables";
import docsUrls from "@/app/base/docsUrls";
import { useSendAnalytics, useWindowTitle } from "@/app/base/hooks";
import { useGetURLId } from "@/app/base/hooks/urls";
import settingsURLs from "@/app/settings/urls";
import machineSelectors from "@/app/store/machine/selectors";
import { MachineMeta } from "@/app/store/machine/types";
import { isMachineDetails, useCanEditStorage } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { isId } from "@/app/utils";

const MachineStorage = (): React.ReactElement => {
  const id = useGetURLId(MachineMeta.PK);
  const sendAnalytics = useSendAnalytics();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );
  const canEditStorage = useCanEditStorage(machine);

  useWindowTitle(`${`${machine?.fqdn} ` || "Machine"} storage`);

  if (isId(id) && isMachineDetails(machine)) {
    return (
      <>
        {canEditStorage && <ChangeStorageLayoutMenu systemId={id} />}
        <StorageTables canEditStorage={canEditStorage} node={machine} />
        <Strip shallow>
          <p>
            Learn more about deploying{" "}
            <ExternalLink
              data-testid="docs-footer-link"
              onClick={() => {
                sendAnalytics(
                  "Machine storage",
                  "Click link to MAAS docs",
                  "Windows"
                );
              }}
              to={docsUrls.windowsImages}
            >
              Windows
            </ExternalLink>
          </p>
          <p>
            Change the default layout in{" "}
            <Link to={settingsURLs.storage}>Settings &rsaquo; Storage</Link>
          </p>
        </Strip>
      </>
    );
  }
  return <Spinner text="Loading..." />;
};

export default MachineStorage;
