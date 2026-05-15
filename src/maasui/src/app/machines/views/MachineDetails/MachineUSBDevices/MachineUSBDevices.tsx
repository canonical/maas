import type { ReactElement } from "react";

import { useSelector } from "react-redux";

import NodeDevicesTable from "@/app/base/components/node/NodeDevicesTable";
import { useWindowTitle } from "@/app/base/hooks";
import { useGetURLId } from "@/app/base/hooks/urls";
import machineSelectors from "@/app/store/machine/selectors";
import { MachineMeta } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import { NodeDeviceBus } from "@/app/store/nodedevice/types";
import type { RootState } from "@/app/store/root/types";

const MachineUSBDevices = (): ReactElement | null => {
  const id = useGetURLId(MachineMeta.PK);
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );
  useWindowTitle(`${`${machine?.fqdn || "Machine"} `} USB devices`);

  if (isMachineDetails(machine)) {
    return <NodeDevicesTable bus={NodeDeviceBus.USB} node={machine} />;
  }
  return null;
};

export default MachineUSBDevices;
