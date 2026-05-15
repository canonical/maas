import type { ReactElement, ReactNode } from "react";

import { Button, Col, List, Row, Tooltip } from "@canonical/react-components";
import { useLocation } from "react-router";

import { ExpandedState } from "../NodeNetworkTab/NodeNetworkTab";

import type {
  Selected,
  SetSelected,
} from "@/app/base/components/node/networking/types";
import { useIsAllNetworkingDisabled } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { default as AddDeviceInterface } from "@/app/devices/components/DeviceNetwork/AddInterface";
import AddBondForm from "@/app/machines/views/MachineDetails/MachineNetwork/AddBondForm";
import AddBridgeForm from "@/app/machines/views/MachineDetails/MachineNetwork/AddBridgeForm";
import AddInterface from "@/app/machines/views/MachineDetails/MachineNetwork/AddInterface";
import type { Node } from "@/app/store/types/node";

type Action = {
  disabled: [boolean, string?][];
  label: string;
  state: ExpandedState;
};

type NetworkActionRowProps = {
  extraActions?: Action[];
  node: Node;
  rightContent?: ReactNode;
  selected?: Selected[];
  setSelected?: SetSelected;
};

export const NETWORK_DISABLED_MESSAGE =
  "Network can't be modified for this machine.";

const NetworkActionRow = ({
  extraActions,
  node,
  rightContent,
  selected,
  setSelected,
}: NetworkActionRowProps): ReactElement | null => {
  const isAllNetworkingDisabled = useIsAllNetworkingDisabled(node);
  const { openSidePanel } = useSidePanel();
  const { pathname } = useLocation();
  const isMachinesPage = pathname.startsWith("/machine");

  const actions: Action[] = [
    {
      disabled: [[isAllNetworkingDisabled, NETWORK_DISABLED_MESSAGE]],
      label: "Add interface",
      state: ExpandedState.ADD_PHYSICAL,
    },
    ...(extraActions || []),
  ];

  const handleButtonClick = (state: ExpandedState) => {
    const expandedStateMap: Partial<Record<ExpandedState, () => void>> = {
      [ExpandedState.ADD_PHYSICAL]: isMachinesPage
        ? () => {
            openSidePanel({
              component: AddInterface,
              title: "Add interface",
              props: {
                systemId: node.system_id,
              },
            });
          }
        : () => {
            openSidePanel({
              component: AddDeviceInterface,
              title: "Add interface",
              props: {
                systemId: node.system_id,
              },
            });
          },
      [ExpandedState.ADD_BOND]: () => {
        openSidePanel({
          component: AddBondForm,
          title: "Add bond",
          props: {
            systemId: node.system_id,
            selected: selected ?? [],
            setSelected: setSelected ?? (() => {}),
          },
          size: "large",
        });
      },
      [ExpandedState.ADD_BRIDGE]: () => {
        openSidePanel({
          component: AddBridgeForm,
          title: "Add bridge",
          props: {
            systemId: node.system_id,
            selected: selected ?? [],
            setSelected: setSelected ?? (() => {}),
          },
          size: "large",
        });
      },
    };
    return expandedStateMap[state]?.();
  };

  const buttons = actions.map((item) => {
    // Check if there is any reason to disable the button.
    const [disabled, tooltip] =
      item.disabled.find(([disabled]) => disabled) || [];
    const button = (
      <Button
        data-testid={item.state}
        disabled={disabled}
        onClick={() => handleButtonClick(item.state)}
      >
        {item.label}
      </Button>
    );
    // Display a tooltip if the disabled item provided a message.
    if (tooltip) {
      return (
        <Tooltip data-testid={`${item.state}-tooltip`} message={tooltip}>
          {button}
        </Tooltip>
      );
    }
    return button;
  });

  return (
    <Row>
      <Col size={8}>
        <List className="u-no-margin--bottom" inline items={buttons} />
      </Col>
      <Col className="u-align--right" size={4}>
        {rightContent}
      </Col>
    </Row>
  );
};

export default NetworkActionRow;
