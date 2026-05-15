import { useState } from "react";
import "./_index.scss";

import { GenericTable } from "@canonical/maas-react-components";
import type { RowSelectionState } from "@tanstack/react-table";

import BulkActions from "./BulkActions";
import type { AvailableStorageRow } from "./useAvailableStorageColumns/useAvailableStorageColumns";
import useAvailableStorageColumns from "./useAvailableStorageColumns/useAvailableStorageColumns";

import { useSidePanel } from "@/app/base/side-panel-context";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import {
  diskAvailable,
  isDatastore,
  isDisk,
  nodeIsMachine,
  partitionAvailable,
} from "@/app/store/utils";

// Actions that are performed on multiple devices at once
export enum BulkAction {
  CREATE_DATASTORE = "createDatastore",
  CREATE_RAID = "createRaid",
  CREATE_VOLUME_GROUP = "createVolumeGroup",
  UPDATE_DATASTORE = "updateDatastore",
}

type Props = {
  canEditStorage: boolean;
  node: ControllerDetails | MachineDetails;
};

/**
 * Returns whether a storage device is available.
 * @param storageDevice - the disk or partition to check.
 * @returns whether a storage device is available.
 */
const isAvailable = (storageDevice: AvailableStorageRow) => {
  if (isDatastore(storageDevice.filesystem)) {
    return false;
  }

  if (isDisk(storageDevice)) {
    return diskAvailable(storageDevice);
  }
  return partitionAvailable(storageDevice);
};

const AvailableStorageTable = ({
  canEditStorage,
  node,
}: Props): React.ReactElement => {
  const isMachine = nodeIsMachine(node);
  const { isOpen } = useSidePanel();
  const actionsDisabled = !canEditStorage || isOpen;
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const columns = useAvailableStorageColumns({
    isMachine,
    actionsDisabled,
    systemId: node.system_id,
  });

  const rows: AvailableStorageRow[] = [];

  node.disks.forEach((disk) => {
    if (isAvailable(disk)) {
      rows.push(disk);
    }

    if (disk.partitions) {
      disk.partitions.forEach((partition) => {
        if (isAvailable(partition)) {
          rows.push({ ...partition, parentDisk: disk });
        }
      });
    }
  });

  const extractSelected = (
    data: AvailableStorageRow[],
    rowSelection: RowSelectionState
  ): AvailableStorageRow[] => {
    const result: AvailableStorageRow[] = [];
    const ids = Object.entries(rowSelection)
      .filter(([_, value]) => value)
      .map(([key]) => key);

    data.forEach((item) => {
      if (ids.includes(item.id.toString())) {
        result.push(item);
      }
    });

    return result;
  };

  return (
    <>
      <GenericTable
        columns={columns}
        data={rows}
        isLoading={false}
        noData="No available disks or partitions."
        selection={
          isMachine
            ? {
                rowSelection,
                setRowSelection,
                filterSelectable: (_) => !actionsDisabled,
                disabledSelectionTooltip:
                  "This machine's disks cannot be modified.",
                rowSelectionLabelKey: "name",
              }
            : undefined
        }
        variant="regular"
      />
      {isMachine && canEditStorage && (
        <BulkActions
          selected={extractSelected(rows, rowSelection)}
          systemId={node.system_id}
        />
      )}
    </>
  );
};

export default AvailableStorageTable;
