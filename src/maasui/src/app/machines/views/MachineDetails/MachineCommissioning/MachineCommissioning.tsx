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
import { TestStatusStatus } from "@/app/store/types/node";
import { isId } from "@/app/utils";

export enum Label {
  Title = "Commissioning",
}

const MachineCommissioning = (): React.ReactElement => {
  const dispatch = useDispatch();
  const id = useGetURLId(MachineMeta.PK);
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );
  const scriptResults = useSelector((state: RootState) =>
    scriptResultSelectors.getByNodeId(state, id)
  );
  const commissioningResults = useSelector((state: RootState) =>
    scriptResultSelectors.getCommissioningByNodeId(state, id)
  );
  const loading = useSelector((state: RootState) =>
    scriptResultSelectors.loading(state)
  );
  const isDetails = isMachineDetails(machine);
  const previousCommissioningStatus = usePrevious(
    isDetails ? machine.commissioning_status.status : null,
    true
  );
  useWindowTitle(`${machine?.fqdn || "Machine"} commissioning`);

  useEffect(() => {
    if (
      isId(id) &&
      isDetails &&
      !loading &&
      (!scriptResults?.length ||
        // Refetch the script results when the commissioning status changes to
        // pending, otherwise the new script results won't be associated with
        // the machine.
        (machine.commissioning_status.status === TestStatusStatus.PENDING &&
          previousCommissioningStatus !== machine.commissioning_status.status))
    ) {
      dispatch(scriptResultActions.getByNodeId(id));
    }
  }, [
    dispatch,
    previousCommissioningStatus,
    scriptResults,
    loading,
    machine,
    id,
    isDetails,
  ]);

  if (isId(id) && isDetails && scriptResults?.length) {
    return (
      <div aria-label={Label.Title}>
        {commissioningResults?.length && commissioningResults.length > 0 ? (
          <NodeTestsTable node={machine} scriptResults={commissioningResults} />
        ) : null}
      </div>
    );
  }
  return <Spinner aria-label={Label.Title} text="Loading..." />;
};

export default MachineCommissioning;
