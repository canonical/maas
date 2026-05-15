import type { ReactElement } from "react";
import { useState } from "react";

import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import MachineNetworkActions from "./MachineNetworkActions";

import DHCPTable from "@/app/base/components/DHCPTable";
import NodeNetworkTab from "@/app/base/components/NodeNetworkTab";
import NetworkTable from "@/app/base/components/node/networking/NetworkTable";
import type { Selected } from "@/app/base/components/node/networking/types";
import { useWindowTitle } from "@/app/base/hooks";
import { useGetURLId } from "@/app/base/hooks/urls";
import machineSelectors from "@/app/store/machine/selectors";
import { MachineMeta } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";

const MachineNetwork = (): ReactElement => {
  const id = useGetURLId(MachineMeta.PK);
  const [selected, setSelected] = useState<Selected[]>([]);
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );

  useWindowTitle(`${machine?.fqdn ? `${machine?.fqdn} ` : "Machine"} network`);

  if (!machine || !isMachineDetails(machine)) {
    return <Spinner aria-label="Loading machine" text="Loading..." />;
  }

  return (
    <NodeNetworkTab
      actions={(expanded) => (
        <MachineNetworkActions
          expanded={expanded}
          selected={selected}
          setSelected={setSelected}
          systemId={id!}
        />
      )}
      aria-label="Machine network"
      dhcpTable={() => (
        <DHCPTable
          className="u-no-padding--top"
          modelName={MachineMeta.MODEL}
          node={machine}
        />
      )}
      interfaceTable={(_, setExpanded) => (
        <NetworkTable
          node={machine}
          setExpanded={setExpanded}
          setSelected={setSelected}
        />
      )}
    />
  );
};

export default MachineNetwork;
