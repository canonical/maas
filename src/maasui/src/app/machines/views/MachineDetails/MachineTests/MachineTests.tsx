import { useEffect } from "react";

import { Spinner } from "@canonical/react-components";
import { usePrevious } from "@canonical/react-components/dist/hooks";
import { useDispatch, useSelector } from "react-redux";

import NodeTestsTable from "@/app/base/components/node/NodeTestsTable/components/NodeTestsTable";
import { HardwareType } from "@/app/base/enum";
import { useWindowTitle } from "@/app/base/hooks";
import { useGetURLId } from "@/app/base/hooks/urls";
import machineSelectors from "@/app/store/machine/selectors";
import { MachineMeta } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { scriptResultActions } from "@/app/store/scriptresult";
import scriptResultSelectors from "@/app/store/scriptresult/selectors";
import type { ScriptResult } from "@/app/store/scriptresult/types";
import { TestStatusStatus } from "@/app/store/types/node";
import { isId } from "@/app/utils";

/**
 * Group items by key
 * @param items
 * @param key
 */
const groupByKey = <I,>(items: I[], key: keyof I): Record<string, I[]> =>
  items.reduce((obj, item) => {
    obj[item[key]] = obj[item[key]] || [];
    obj[item[key]].push(item);
    return obj;
  }, Object.create(null));

export enum Label {
  Title = "Tests",
}
const MachineTests = (): React.ReactElement => {
  const dispatch = useDispatch();
  const id = useGetURLId(MachineMeta.PK);

  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );
  const previousTestingStatus = usePrevious(machine?.testing_status, true);
  const scriptResults = useSelector((state: RootState) =>
    scriptResultSelectors.getByNodeId(state, id)
  );
  const hardwareResults = useSelector((state: RootState) =>
    scriptResultSelectors.getHardwareTestingByNodeId(state, id)
  );
  const storageResults = useSelector((state: RootState) =>
    scriptResultSelectors.getStorageTestingByNodeId(state, id)
  );
  const otherResults = useSelector((state: RootState) =>
    scriptResultSelectors.getOtherTestingByNodeId(state, id)
  );
  const loading = useSelector(scriptResultSelectors.loading);
  useWindowTitle(`${machine?.fqdn || "Machine"} tests`);
  const isDetails = isMachineDetails(machine);

  // load script results on mount
  useEffect(() => {
    if (isId(id)) {
      dispatch(scriptResultActions.getByNodeId(id));
    }
  }, [dispatch, id]);

  useEffect(() => {
    if (
      isId(id) &&
      !loading &&
      // Refetch the script results when the testing status changes to
      // pending, otherwise the new script results won't be associated with
      // the machine.
      machine?.testing_status === TestStatusStatus.PENDING &&
      previousTestingStatus !== machine?.testing_status
    ) {
      dispatch(scriptResultActions.getByNodeId(id));
    }
  }, [dispatch, previousTestingStatus, loading, machine, id]);

  if (isId(id) && isDetails && scriptResults?.length) {
    return (
      <div aria-label={Label.Title}>
        {hardwareResults?.length && hardwareResults.length > 0
          ? Object.entries(groupByKey(hardwareResults, "hardware_type")).map(
              ([hardware_type, scriptResults]: [string, ScriptResult[]]) => {
                let title: string | null = null;
                if (scriptResults[0].hardware_type === HardwareType.Network) {
                  const { mac_address, name } =
                    scriptResults[0].parameters?.interface?.value || {};
                  if (name && mac_address) {
                    title = `${name} (${mac_address})`;
                  } else {
                    title = name || null;
                  }
                }
                return (
                  <div key={hardware_type}>
                    <h4 data-testid="hardware-heading">
                      {HardwareType[parseInt(hardware_type, 0)]}
                    </h4>
                    {title && (
                      <h5 data-testid="hardware-device-heading">{title}</h5>
                    )}
                    <NodeTestsTable
                      node={machine}
                      scriptResults={scriptResults}
                    />
                  </div>
                );
              }
            )
          : null}
        {storageResults?.length && storageResults.length > 0 ? (
          <>
            <h4 data-testid="hardware-heading">Storage</h4>
            {Object.entries(
              groupByKey(storageResults, "physical_blockdevice")
            ).map(
              ([physical_blockdevice, scriptResults]: [
                string,
                ScriptResult[],
              ]) => {
                const { model, name, serial } =
                  scriptResults[0]?.parameters?.storage?.value || {};
                let title = name ? `/dev/${name}` : null;
                if (name && (model || serial)) {
                  const additional = [`model: ${model}`, `serial: ${serial}`]
                    .filter(Boolean)
                    .join(", ");
                  title = `${title} (${additional})`;
                }
                return (
                  <div key={physical_blockdevice}>
                    {title && <h5 data-testid="storage-heading">{title}</h5>}
                    <NodeTestsTable
                      node={machine}
                      scriptResults={scriptResults}
                    />
                  </div>
                );
              }
            )}
          </>
        ) : null}
        {otherResults?.length && otherResults.length > 0 ? (
          <>
            <h4 data-testid="hardware-heading">Other Results</h4>
            {Object.entries(groupByKey(otherResults, "hardware_type")).map(
              ([hardware_type, scriptResults]: [string, ScriptResult[]]) => {
                return (
                  <div key={hardware_type}>
                    <NodeTestsTable
                      node={machine}
                      scriptResults={scriptResults}
                    />
                  </div>
                );
              }
            )}
          </>
        ) : null}
      </div>
    );
  }
  return <Spinner aria-label={Label.Title} text="Loading..." />;
};

export default MachineTests;
