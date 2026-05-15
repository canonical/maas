import type { ReactElement } from "react";
import { useEffect } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { Button } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import useNodeDevicesTableColumns, {
  filterCells,
} from "@/app/base/components/node/NodeDevicesTable/useNodeDevicesTableColumns/useNodeDevicesTableColumns";
import { HardwareType } from "@/app/base/enum";
import { useSidePanel } from "@/app/base/side-panel-context";
import CommissionForm from "@/app/machines/components/MachineForms/MachineActionFormWrapper/CommissionForm";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import { nodeDeviceActions } from "@/app/store/nodedevice";
import nodeDeviceSelectors from "@/app/store/nodedevice/selectors";
import type { NodeDevice } from "@/app/store/nodedevice/types";
import { NodeDeviceBus } from "@/app/store/nodedevice/types";
import type { RootState } from "@/app/store/root/types";
import type { NodeNumaNode } from "@/app/store/types/node";
import { NodeActions, NodeStatusCode } from "@/app/store/types/node";
import { nodeIsMachine } from "@/app/store/utils";

import "./index.scss";

type NodeDevicesTableProps = {
  bus: NodeDeviceBus;
  node: ControllerDetails | MachineDetails;
};

type HardwareGroup = "Generic" | "GPU" | "Network" | "Storage";

export type GroupedNodeDevice = NodeDevice & {
  hardware_group: HardwareGroup;
  numa_node: NodeNumaNode | undefined;
};

const NodeDevicesTable = ({
  bus,
  node,
}: NodeDevicesTableProps): ReactElement => {
  const dispatch = useDispatch();
  const { openSidePanel } = useSidePanel();
  const isMachine = nodeIsMachine(node);
  const canBeCommissioned =
    isMachine && node.actions.includes(NodeActions.COMMISSION);
  const nodeDevices = useSelector((state: RootState) =>
    nodeDeviceSelectors.getByNodeId(state, node.id)
  );
  const nodeDevicesLoading = useSelector(nodeDeviceSelectors.loading);
  const loaded = nodeDevices.some(
    (nodeDevice) => nodeDevice.node_id === node.id
  );

  useEffect(() => {
    if (!loaded) {
      dispatch(nodeDeviceActions.getByNodeId(node.system_id));
    }
  }, [dispatch, loaded, node.system_id]);

  const devices = nodeDevices
    .map((nodeDevice): GroupedNodeDevice => {
      let hardwareGroup: HardwareGroup;
      switch (nodeDevice.hardware_type) {
        case HardwareType.Network:
          hardwareGroup = "Network";
          break;
        case HardwareType.Storage:
          hardwareGroup = "Storage";
          break;
        case HardwareType.GPU:
          hardwareGroup = "GPU";
          break;
        default:
          hardwareGroup = "Generic";
      }
      const numaNode = node.numa_nodes.find(
        (numa) => numa.id === nodeDevice.numa_node_id
      );
      return {
        ...nodeDevice,
        hardware_group: hardwareGroup,
        numa_node: numaNode,
      };
    })
    .filter((nodeDevice) => nodeDevice.bus === bus);

  let warningMessage = "";
  if (canBeCommissioned) {
    warningMessage =
      "Try commissioning this machine to load PCI and USB device information.";
  } else if (isMachine) {
    if (node.locked) {
      warningMessage =
        "The machine is locked. Unlock and release this machine before commissioning to load PCI and USB device information.";
    } else if (node.status_code === NodeStatusCode.FAILED_TESTING) {
      warningMessage =
        "Override failed testing before commissioning to load PCI and USB device information.";
    } else if (node.status_code === NodeStatusCode.DEPLOYED) {
      warningMessage =
        "Release this machine before commissioning to load PCI and USB device information.";
    } else if (node.status_code === NodeStatusCode.COMMISSIONING) {
      warningMessage = "Commissioning is currently in progress...";
    } else {
      warningMessage = "Commissioning cannot be run at this time.";
    }
  }

  const columns = useNodeDevicesTableColumns(bus, node);

  return (
    <>
      <GenericTable
        className={`node-devices-table--${
          bus === NodeDeviceBus.PCIE ? "pci" : "usb"
        }`}
        columns={columns}
        data={devices}
        filterCells={filterCells}
        groupBy={["hardware_group"]}
        isLoading={nodeDevicesLoading}
        noData={
          bus === NodeDeviceBus.PCIE ? (
            <>
              <h4>No PCI information</h4>
              {warningMessage && (
                <p className="u-sv1" data-testid="no-devices-warning">
                  {warningMessage}
                </p>
              )}
              {canBeCommissioned && (
                <Button
                  appearance="positive"
                  data-testid="commission-machine"
                  onClick={() => {
                    openSidePanel({
                      component: CommissionForm,
                      title: "Commission machine",
                      props: {
                        isViewingDetails: true,
                      },
                    });
                  }}
                >
                  Commission
                </Button>
              )}
            </>
          ) : (
            <>
              <h4>No USB information</h4>
              {isMachine && (
                <p className="u-sv1" data-testid="no-usb-warning">
                  No USB devices discovered during commissioning.
                </p>
              )}
            </>
          )
        }
        pinGroup={[
          { value: "Network", isTop: true },
          { value: "Storage", isTop: true },
          { value: "GPU", isTop: true },
          { value: "Generic", isTop: false },
        ]}
        showChevron
      />
    </>
  );
};

export default NodeDevicesTable;
