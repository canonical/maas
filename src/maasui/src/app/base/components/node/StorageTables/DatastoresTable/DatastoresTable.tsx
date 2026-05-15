import type { ReactElement } from "react";

import { GenericTable } from "@canonical/maas-react-components";

import useDatastoresTableColumns from "@/app/base/components/node/StorageTables/DatastoresTable/useDatastoresTableColumns/useDatastoresTableColumns";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import type { Disk } from "@/app/store/types/node";
import { isDatastore, nodeIsMachine } from "@/app/store/utils";

export enum DatastoreAction {
  DELETE = "deleteDisk",
}

type Props = {
  canEditStorage: boolean;
  node: ControllerDetails | MachineDetails;
};

export type DatastoreRow = {
  id: string;
  name: string;
  size: number;
  fstype: string;
  mount_point: string;
  disk: Disk;
  systemId: string;
};

const generateDatastoreRowData = (
  node: ControllerDetails | MachineDetails
): DatastoreRow[] => {
  const data: DatastoreRow[] = [];

  node.disks.forEach((disk) => {
    if (!disk.filesystem || !isDatastore(disk.filesystem)) {
      return;
    }

    data.push({
      id: `${disk.filesystem.fstype}-${disk.filesystem.id}`,
      name: disk.name,
      size: disk.size,
      fstype: disk.filesystem.fstype,
      mount_point: disk.filesystem.mount_point,
      disk,
      systemId: node.system_id,
    });
  });

  return data;
};

const DatastoresTable = ({ canEditStorage, node }: Props): ReactElement => {
  const isMachine = nodeIsMachine(node);

  const columns = useDatastoresTableColumns(canEditStorage, isMachine);
  const data = generateDatastoreRowData(node);

  return (
    <GenericTable
      columns={columns}
      data={data}
      isLoading={false}
      noData="No datastores detected."
      sorting={[{ id: "name", desc: false }]}
      style={{ marginBottom: "1.5rem" }}
      variant="regular"
    />
  );
};

export default DatastoresTable;
