import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import NodeScripts from "@/app/base/components/node/NodeScripts/NodeScripts";
import { useWindowTitle } from "@/app/base/hooks";
import { useGetURLId } from "@/app/base/hooks/urls";
import urls from "@/app/base/urls";
import machineSelectors from "@/app/store/machine/selectors";
import { MachineMeta } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";

export enum Label {
  Loading = "Loading scripts",
}

const MachineScript = (): React.ReactElement => {
  const systemId = useGetURLId(MachineMeta.PK);
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  useWindowTitle(`${`${machine?.fqdn} ` || "Machine"} scripts`);

  if (!machine || !isMachineDetails(machine)) {
    return <Spinner aria-label={Label.Loading} text="Loading..." />;
  }
  return (
    <NodeScripts
      node={machine}
      urls={{
        index: urls.machines.machine.scriptsResults.index,
        commissioning: urls.machines.machine.scriptsResults.commissioning,
        deployment: urls.machines.machine.scriptsResults.deployment,
        testing: urls.machines.machine.scriptsResults.testing,
      }}
    />
  );
};

export default MachineScript;
