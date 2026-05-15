import type { Dispatch, ReactElement, SetStateAction } from "react";

import { Button } from "@canonical/react-components";
import { useSelector } from "react-redux";

import NetworkActionRow from "@/app/base/components/NetworkActionRow";
import { NETWORK_DISABLED_MESSAGE } from "@/app/base/components/NetworkActionRow/NetworkActionRow";
import type { Expanded } from "@/app/base/components/NodeNetworkTab/NodeNetworkTab";
import { ExpandedState } from "@/app/base/components/NodeNetworkTab/NodeNetworkTab";
import type { Selected } from "@/app/base/components/node/networking/types";
import { useIsAllNetworkingDisabled, useSendAnalytics } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import TestMachineForm from "@/app/machines/components/MachineForms/MachineActionFormWrapper/TestMachineForm";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine, MachineDetails } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import {
  getInterfaceById,
  getInterfaceType,
  getLinkFromNic,
} from "@/app/store/utils";

type Action = {
  disabled: [boolean, string?][];
  label: string;
  state: ExpandedState;
};

type MachineNetworkActionsProps = {
  expanded: Expanded | null;
  selected: Selected[];
  setSelected: Dispatch<SetStateAction<Selected[]>>;
  systemId: Machine["system_id"];
};

// Check if any of the selected interfaces includes the provided type.
const selectedIncludesType = (
  machine: MachineDetails,
  selected: Selected[],
  interfaceType: NetworkInterfaceTypes
): boolean =>
  selected.some(({ nicId, linkId }) => {
    const nic = getInterfaceById(machine, nicId, linkId);
    const link = getLinkFromNic(nic, linkId);
    return interfaceType === getInterfaceType(machine, nic, link);
  });

// Check if any of the selected interfaces does not have the provided type.
const selectedAllOfType = (
  machine: MachineDetails,
  selected: Selected[],
  interfaceType: NetworkInterfaceTypes
): boolean =>
  selected.every(({ nicId, linkId }) => {
    const nic = getInterfaceById(machine, nicId, linkId);
    const link = getLinkFromNic(nic, linkId);
    return interfaceType === getInterfaceType(machine, nic, link);
  });

// Check if any of the selected interfaces has a different VLAN.
const selectedDifferentVLANs = (
  machine: MachineDetails,
  selected: Selected[]
): boolean => {
  let firstVLAN: number;
  return selected.some(({ nicId, linkId }) => {
    const nic = getInterfaceById(machine, nicId, linkId);
    // Store the first VLAN.
    if (nic && typeof firstVLAN !== "number") {
      firstVLAN = nic.vlan_id;
    }
    // Use the first VLAN as the predicate for all other selected interfaces.
    return nic?.vlan_id !== firstVLAN;
  });
};

const MachineNetworkActions = ({
  selected,
  systemId,
  setSelected,
}: MachineNetworkActionsProps): ReactElement | null => {
  const { openSidePanel } = useSidePanel();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(machine);
  const sendAnalytics = useSendAnalytics();

  if (!isMachineDetails(machine)) {
    return null;
  }

  const actions: Action[] = [
    {
      disabled: [
        [isAllNetworkingDisabled, NETWORK_DISABLED_MESSAGE],
        [selected.length === 0, "No interfaces are selected"],
        [selected.length === 1, "A bond must include more than one interface"],
        [
          !selectedAllOfType(machine, selected, NetworkInterfaceTypes.PHYSICAL),
          "A bond can only include physical interfaces",
        ],
        [
          selectedDifferentVLANs(machine, selected),
          "All selected interfaces must be on the same VLAN",
        ],
      ],
      label: "Create bond",
      state: ExpandedState.ADD_BOND,
    },
    {
      disabled: [
        [isAllNetworkingDisabled, NETWORK_DISABLED_MESSAGE],
        [selected.length === 0, "No interfaces are selected"],
        [
          selectedIncludesType(machine, selected, NetworkInterfaceTypes.ALIAS),
          "A bridge can not be created from an alias",
        ],
        [
          selectedIncludesType(machine, selected, NetworkInterfaceTypes.BRIDGE),
          "A bridge can not be created from another bridge",
        ],
      ],
      label: "Create bridge",
      state: ExpandedState.ADD_BRIDGE,
    },
  ];

  return (
    <NetworkActionRow
      extraActions={actions}
      node={machine}
      rightContent={
        <Button
          className="u-no-margin--bottom"
          disabled={isAllNetworkingDisabled}
          onClick={() => {
            openSidePanel({
              component: TestMachineForm,
              title: "Test machine",
              props: {
                applyConfiguredNetworking: true,
                isViewingDetails: true,
              },
            });
            sendAnalytics(
              "Machine details",
              "Validate network configuration",
              "Network tab"
            );
          }}
        >
          Validate network configuration
        </Button>
      }
      selected={selected}
      setSelected={setSelected}
    />
  );
};

export default MachineNetworkActions;
