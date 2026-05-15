import { useMemo } from "react";

import type { Column, ColumnDef, Row } from "@tanstack/react-table";
import pluralize from "pluralize";
import { Link } from "react-router";

import DoubleRow from "@/app/base/components/DoubleRow";
import type { GroupedNodeDevice } from "@/app/base/components/node/NodeDevicesTable/NodeDevicesTable";
import urls from "@/app/base/urls";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import { NodeDeviceBus } from "@/app/store/nodedevice/types";
import { nodeIsMachine } from "@/app/store/utils";

export type NodeDeviceColumnDef = ColumnDef<
  GroupedNodeDevice,
  Partial<GroupedNodeDevice>
>;

export const filterCells = (
  row: Row<GroupedNodeDevice>,
  column: Column<GroupedNodeDevice>
): boolean => {
  return row.getIsGrouped() ? "hardware_group" === column.id : true;
};

const useNodeDevicesTableColumns = (
  bus: NodeDeviceBus,
  node: ControllerDetails | MachineDetails
): NodeDeviceColumnDef[] => {
  const isMachine = nodeIsMachine(node);
  const storageURL = isMachine
    ? urls.machines.machine.storage({ id: node.system_id })
    : urls.controllers.controller.storage({ id: node.system_id });
  const networkURL = isMachine
    ? urls.machines.machine.network({ id: node.system_id })
    : urls.controllers.controller.network({ id: node.system_id });

  return useMemo(
    () => [
      {
        id: "hardware_group",
        accessorKey: "hardware_group",
        enableSorting: false,
        header: "",
        cell: ({
          row: {
            original: { hardware_group },
            getLeafRows,
            getIsGrouped,
          },
        }: {
          row: Row<GroupedNodeDevice>;
        }) =>
          getIsGrouped() ? (
            <DoubleRow
              primary={
                <strong>
                  {hardware_group === "Storage" ? (
                    <Link to={storageURL}>{hardware_group}</Link>
                  ) : hardware_group === "Network" ? (
                    <Link to={networkURL}>{hardware_group}</Link>
                  ) : (
                    hardware_group
                  )}
                </strong>
              }
              secondary={pluralize("device", getLeafRows().length, true)}
            />
          ) : null,
      },
      {
        id: "vendor",
        accessorKey: "vendor_name",
        enableSorting: false,
        header: () => (
          <>
            <span>Vendor</span>
            <br />
            <span>ID</span>
          </>
        ),
        cell: ({
          row: {
            original: { vendor_name, vendor_id },
          },
        }: {
          row: Row<GroupedNodeDevice>;
        }) => (
          <DoubleRow
            primary={vendor_name}
            primaryTitle={vendor_name}
            secondary={vendor_id}
          />
        ),
      },
      {
        id: "product",
        accessorKey: "product_name",
        enableSorting: false,
        header: () => (
          <>
            <span>Product</span>
            <br />
            <span>ID</span>
          </>
        ),
        cell: ({
          row: {
            original: { product_name, product_id },
          },
        }: {
          row: Row<GroupedNodeDevice>;
        }) => (
          <DoubleRow
            primary={product_name || "—"}
            primaryTitle={product_name}
            secondary={product_id}
          />
        ),
      },
      {
        id: "driver",
        accessorKey: "commissioning_driver",
        enableSorting: false,
        header: "Driver",
      },
      {
        id: "numa_node",
        accessorKey: "numa_node",
        enableSorting: false,
        header: "NUMA node",
        cell: ({
          row: {
            original: { numa_node },
          },
        }: {
          row: Row<GroupedNodeDevice>;
        }) => numa_node?.index ?? "",
      },
      {
        id: "bus",
        accessorKey: "bus",
        enableSorting: false,
        header: () =>
          bus === NodeDeviceBus.PCIE ? (
            "PCI address"
          ) : (
            <>
              <span>Bus address</span>
              <br />
              <span>Device address</span>
            </>
          ),
        cell: ({
          row: {
            original: { pci_address, bus_number, device_number },
          },
        }: {
          row: Row<GroupedNodeDevice>;
        }) =>
          bus === NodeDeviceBus.PCIE ? (
            pci_address
          ) : (
            <DoubleRow primary={bus_number} secondary={device_number} />
          ),
      },
    ],
    [bus, networkURL, storageURL]
  );
};

export default useNodeDevicesTableColumns;
