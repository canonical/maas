import { useSelector } from "react-redux";

import { useIsAllNetworkingDisabled } from "@/app/base/hooks";
import { useGetURLId } from "@/app/base/hooks/urls";
import MachineNotifications from "@/app/machines/views/MachineDetails/MachineNotifications";
import machineSelectors from "@/app/store/machine/selectors";
import { MachineMeta } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";

const NetworkNotifications = (): React.ReactElement | null => {
  const id = useGetURLId(MachineMeta.PK);
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(machine);

  if (!isMachineDetails(machine)) {
    return null;
  }

  return (
    <MachineNotifications
      notifications={[
        {
          active: !machine.on_network,
          content: "Machine must be connected to a network.",
          severity: "negative",
          title: "Error:",
        },
        {
          active: isAllNetworkingDisabled,
          content:
            "Interface configuration cannot be modified unless the machine is New, Ready, Allocated or Broken.",
        },
        {
          active: machine.osystem === "custom",
          content:
            "Custom images may require special preparation to support custom network configuration.",
          severity: "caution",
          title: "Important:",
        },
      ]}
    />
  );
};

export default NetworkNotifications;
