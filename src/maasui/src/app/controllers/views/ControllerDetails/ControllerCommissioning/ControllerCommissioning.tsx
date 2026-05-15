import { useEffect } from "react";

import { Spinner, usePrevious } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import NodeTestsTable from "@/app/base/components/node/NodeTestsTable/components/NodeTestsTable";
import { useWindowTitle } from "@/app/base/hooks";
import controllerSelectors from "@/app/store/controller/selectors";
import type { Controller, ControllerMeta } from "@/app/store/controller/types";
import { isControllerDetails } from "@/app/store/controller/utils";
import type { RootState } from "@/app/store/root/types";
import { scriptResultActions } from "@/app/store/scriptresult";
import scriptResultSelectors from "@/app/store/scriptresult/selectors";
import { TestStatusStatus } from "@/app/store/types/node";

type Props = {
  systemId: Controller[ControllerMeta.PK];
};

const ControllerCommissioning = ({
  systemId,
}: Props): React.ReactElement | null => {
  const dispatch = useDispatch();
  const controller = useSelector((state: RootState) =>
    controllerSelectors.getById(state, systemId)
  );
  const scriptResults = useSelector((state: RootState) =>
    scriptResultSelectors.getCommissioningByNodeId(state, systemId)
  );
  const scriptResultsLoading = useSelector((state: RootState) =>
    scriptResultSelectors.loading(state)
  );
  const isDetails = isControllerDetails(controller);
  const previousCommissioningStatus = usePrevious(
    isDetails ? controller.commissioning_status.status : null,
    true
  );
  useWindowTitle(`${`${controller?.hostname}` || "Controller"} commissioning`);

  const shouldFetchResults =
    !scriptResultsLoading &&
    (!scriptResults?.length ||
      // Refetch the script results when the commissioning status changes to
      // pending, otherwise the new script results won't be associated with
      // the controller.
      (isDetails &&
        controller.commissioning_status.status === TestStatusStatus.PENDING &&
        previousCommissioningStatus !==
          controller.commissioning_status.status));
  useEffect(() => {
    if (shouldFetchResults) {
      dispatch(scriptResultActions.getByNodeId(systemId));
    }
  }, [dispatch, shouldFetchResults, systemId]);

  if (!scriptResults || !isDetails) {
    return <Spinner aria-label="Loading script results" text="Loading..." />;
  }
  return <NodeTestsTable node={controller} scriptResults={scriptResults} />;
};

export default ControllerCommissioning;
