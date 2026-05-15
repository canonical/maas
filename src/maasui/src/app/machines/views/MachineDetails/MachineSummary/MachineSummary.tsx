import type { ReactElement } from "react";

import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import NumaCard from "./NumaCard";
import WorkloadCard from "./WorkloadCard";

import NodeSummaryNetworkCard from "@/app/base/components/NodeSummaryNetworkCard";
import HardwareCard from "@/app/base/components/node/HardwareCard";
import OverviewCard from "@/app/base/components/node/OverviewCard";
import TestResults from "@/app/base/components/node/TestResults";
import { HardwareType } from "@/app/base/enum";
import { useWindowTitle } from "@/app/base/hooks";
import { useGetURLId } from "@/app/base/hooks/urls";
import urls from "@/app/base/urls";
import machineSelectors from "@/app/store/machine/selectors";
import { MachineMeta } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import { useFetchMachine } from "@/app/store/machine/utils/hooks";
import type { RootState } from "@/app/store/root/types";
import { NodeStatusCode } from "@/app/store/types/node";
import { isId } from "@/app/utils";

const MachineSummary = (): ReactElement => {
  const id = useGetURLId(MachineMeta.PK);
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );
  useFetchMachine(id);
  useWindowTitle(`${`${machine?.fqdn} ` || "Machine"} details`);

  if (!isId(id) || !machine || !isMachineDetails(machine)) {
    return <Spinner text="Loading" />;
  }

  const networkURL = urls.machines.machine.network({ id });
  const showWorkloadCard = [
    NodeStatusCode.ALLOCATED,
    NodeStatusCode.DEPLOYED,
  ].includes(machine?.status_code);

  return (
    <div className="machine-summary__cards">
      <div className="machine-summary__overview-card">
        <OverviewCard node={machine} />
      </div>
      <div className="machine-summary__hardware-card">
        <HardwareCard node={machine} />
      </div>
      <NumaCard id={id} />
      <div className="machine-summary__network-card">
        <NodeSummaryNetworkCard
          interfaces={isMachineDetails(machine) ? machine.interfaces : null}
          networkURL={networkURL}
          node={machine}
        >
          <p>
            Information about tagged traffic can be seen in the{" "}
            <Link to={networkURL}>Network tab</Link>.
          </p>
          {isMachineDetails(machine) && (
            <TestResults
              hardwareType={HardwareType.Network}
              machine={machine}
            />
          )}
        </NodeSummaryNetworkCard>
      </div>
      {showWorkloadCard ? <WorkloadCard id={id} /> : null}
    </div>
  );
};

export default MachineSummary;
