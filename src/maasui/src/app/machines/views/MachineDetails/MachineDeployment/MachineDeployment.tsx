import { useEffect } from "react";

import { Spinner } from "@canonical/react-components";
import { usePrevious } from "@canonical/react-components/dist/hooks";
import { useDispatch, useSelector } from "react-redux";

import NodeTestsTable from "@/app/base/components/node/NodeTestsTable/components/NodeTestsTable";
import { useWindowTitle } from "@/app/base/hooks";
import { useGetURLId } from "@/app/base/hooks/urls";
import machineSelectors from "@/app/store/machine/selectors";
import { MachineMeta } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { scriptResultActions } from "@/app/store/scriptresult";
import scriptResultSelectors from "@/app/store/scriptresult/selectors";
import { NodeStatus } from "@/app/store/types/node";
import { isId } from "@/app/utils";

export enum Label {
  Title = "Deployment",
}

const MachineDeployment = (): React.ReactElement => {
  const dispatch = useDispatch();
  const id = useGetURLId(MachineMeta.PK);
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );
  const scriptResults = useSelector((state: RootState) =>
    scriptResultSelectors.getByNodeId(state, id)
  );
  const deploymentResults = useSelector((state: RootState) =>
    scriptResultSelectors.getDeploymentByNodeId(state, id)
  );
  const loading = useSelector((state: RootState) =>
    scriptResultSelectors.loading(state)
  );
  const isDetails = isMachineDetails(machine);
  const previousDeploymentStatus = usePrevious(
    isDetails ? machine.status : true
  );
  useWindowTitle(`${machine?.fqdn || "Machine"} deployment`);

  useEffect(() => {
    if (
      id &&
      isId(id) &&
      isDetails &&
      !loading &&
      (!scriptResults?.length ||
        // Refetch the script results when the deployment status changes to
        // pending, otherwise the new script results won't be associated with
        // the machine.
        (machine.status === NodeStatus.DEPLOYING &&
          previousDeploymentStatus !== machine.status))
    ) {
      dispatch(scriptResultActions.getByNodeId(id));
    }
  }, [
    dispatch,
    previousDeploymentStatus,
    scriptResults,
    loading,
    machine,
    id,
    isDetails,
  ]);

  if (isDetails) {
    return (
      <div aria-label={Label.Title}>
        <NodeTestsTable
          isLoading={loading}
          node={machine}
          scriptResults={deploymentResults || []}
        />
      </div>
    );
  }
  return <Spinner aria-label={Label.Title} text="Loading..." />;
};

export default MachineDeployment;
