import type { ComponentType, ReactElement } from "react";

import { useSelector } from "react-redux";

import EditInterface from "../../EditInterface";

import TableMenu from "@/app/base/components/TableMenu";
import type { Props as TableMenuProps } from "@/app/base/components/TableMenu/TableMenu";
import TooltipButton from "@/app/base/components/TooltipButton";
import type {
  Selected,
  SetSelected,
} from "@/app/base/components/node/networking/types";
import { useIsAllNetworkingDisabled } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import AddAliasOrVlan from "@/app/machines/views/MachineDetails/MachineNetwork/AddAliasOrVlan";
import MarkConnectedForm from "@/app/machines/views/MachineDetails/MachineNetwork/MarkConnectedForm";
import { ConnectionState } from "@/app/machines/views/MachineDetails/MachineNetwork/MarkConnectedForm/MarkConnectedForm";
import RemovePhysicalForm from "@/app/machines/views/MachineDetails/MachineNetwork/RemovePhysicalForm";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import {
  isMachineDetails,
  useCanAddVLAN,
  useIsLimitedEditingAllowed,
} from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";
import {
  canAddAlias,
  getInterfaceTypeText,
  hasInterfaceType,
} from "@/app/store/utils";

type NetworkTableActionsProps = {
  link?: NetworkLink | null;
  nic: NetworkInterface;
  selected?: Selected[] | undefined;
  setSelected?: SetSelected | undefined;
  systemId: Machine["system_id"];
};

const NetworkTableActions = ({
  link,
  nic,
  selected,
  setSelected,
  systemId,
}: NetworkTableActionsProps): ReactElement | null => {
  const { openSidePanel } = useSidePanel();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(machine);
  const isLimitedEditingAllowed = useIsLimitedEditingAllowed(nic, machine);
  const canAddVLAN = useCanAddVLAN(machine, nic, link);
  const itCanAddAlias = canAddAlias(machine, nic, link);
  if (!isMachineDetails(machine)) {
    return null;
  }
  const isPhysical = hasInterfaceType(
    NetworkInterfaceTypes.PHYSICAL,
    machine,
    nic,
    link
  );
  const actions: TableMenuProps["links"] = [];
  if (machine) {
    const showDisconnectedWarning = isPhysical && !nic.link_connected;
    if (!nic.link_connected && isPhysical) {
      actions.push({
        children: "Mark as connected...",
        onClick: () => {
          openSidePanel({
            component: MarkConnectedForm,
            title: "Mark as connected",
            props: {
              systemId: machine.system_id,
              link,
              nic,
              connectionState: ConnectionState.MARK_CONNECTED,
            },
          });
        },
      });
    }
    if (nic.link_connected && isPhysical) {
      actions.push({
        children: "Mark as disconnected...",
        onClick: () => {
          openSidePanel({
            component: MarkConnectedForm,
            title: "Mark as disconnected",
            props: {
              systemId: machine.system_id,
              link,
              nic,
              connectionState: ConnectionState.MARK_DISCONNECTED,
            },
          });
        },
      });
    }
    if (
      !isAllNetworkingDisabled &&
      !hasInterfaceType([NetworkInterfaceTypes.ALIAS], machine, nic, link)
    ) {
      actions.push({
        children: itCanAddAlias ? (
          "Add alias..."
        ) : (
          <span className="u-flex">
            <span className="u-flex--grow">Add alias...</span>
            <TooltipButton
              iconName="help"
              message="IP mode needs to be configured for this interface."
              position="top-right"
            />
          </span>
        ),
        disabled: !itCanAddAlias,
        onClick: () => {
          openSidePanel({
            component: AddAliasOrVlan,
            title: "Add alias",
            props: {
              systemId: machine.system_id,
              nic,
              interfaceType: NetworkInterfaceTypes.ALIAS,
            },
          });
        },
      });
    }
    if (
      !isAllNetworkingDisabled &&
      !hasInterfaceType(
        [NetworkInterfaceTypes.ALIAS, NetworkInterfaceTypes.VLAN],
        machine,
        nic,
        link
      )
    ) {
      actions.push({
        children: canAddVLAN ? (
          "Add VLAN..."
        ) : (
          <span className="u-flex">
            <span className="u-flex--grow">Add VLAN...</span>
            <TooltipButton
              iconName="help"
              message="There are no unused VLANS for this interface."
              position="top-right"
            />
          </span>
        ),
        disabled: !canAddVLAN,
        onClick: () => {
          openSidePanel({
            component: AddAliasOrVlan,
            title: "Add VLAN",
            props: {
              systemId: machine.system_id,
              nic,
              interfaceType: NetworkInterfaceTypes.VLAN,
            },
          });
        },
      });
    }
    actions.push({
      children: `Edit ${getInterfaceTypeText(machine, nic, link)}...`,
      onClick: () => {
        if (showDisconnectedWarning) {
          openSidePanel({
            component: MarkConnectedForm,
            title: "Mark as connected",
            props: {
              systemId: machine.system_id,
              link,
              nic,
              connectionState: ConnectionState.DISCONNECTED_WARNING,
            },
          });
        } else if (selected && setSelected) {
          openSidePanel({
            component: EditInterface,
            title: `Edit ${getInterfaceTypeText(machine, nic, link)}`,
            props: {
              selected,
              setSelected,
              systemId: machine.system_id,
              linkId: link?.id,
              nicId: nic.id,
            },
            size: nic.type === NetworkInterfaceTypes.BOND ? "large" : undefined,
          });
        }
      },
    });
    if (!isAllNetworkingDisabled) {
      actions.push({
        children: `Remove ${getInterfaceTypeText(machine, nic, link)}...`,
        onClick: () => {
          openSidePanel({
            // Cast component type to appease TiCS, local compiler shows no error
            component: RemovePhysicalForm as ComponentType<
              Record<string, unknown>
            >,
            title: `Remove ${getInterfaceTypeText(machine, nic, link)}`,
            props: {
              systemId: machine.system_id,
              link,
              nic,
            },
          });
        },
      });
    }
  }
  return (
    <TableMenu
      disabled={isAllNetworkingDisabled && !isLimitedEditingAllowed}
      links={actions}
      position="right"
      title="Take action:"
    />
  );
};

export default NetworkTableActions;
