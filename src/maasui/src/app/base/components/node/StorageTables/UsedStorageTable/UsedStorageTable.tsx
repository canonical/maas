import type { ReactElement } from "react";

import { GenericTable } from "@canonical/maas-react-components";

import useUsedStorageTableColumns from "@/app/base/components/node/StorageTables/UsedStorageTable/useUsedStorageTableColumns/useUsedStorageTableColumns";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import type { Disk, Partition } from "@/app/store/types/node";
import {
  diskAvailable,
  partitionAvailable,
  nodeIsMachine,
} from "@/app/store/utils";

import "./_index.scss";

type UsedStorageTableProps = {
  node: ControllerDetails | MachineDetails;
};

export type UsedStorage = Disk | Partition;

const generateUsedStorageData = (node: ControllerDetails | MachineDetails) => {
  const data: UsedStorage[] = [];

  node.disks.forEach((disk) => {
    if (!diskAvailable(disk)) {
      data.push(disk);
    }

    if (disk.partitions) {
      disk.partitions.forEach((partition) => {
        if (!partitionAvailable(partition)) {
          data.push(partition);
        }
      });
    }
  });

  return data;
};

const UsedStorageTable = ({ node }: UsedStorageTableProps): ReactElement => {
  const columns = useUsedStorageTableColumns(nodeIsMachine(node));
  const data = generateUsedStorageData(node);

  return (
    <GenericTable
      columns={columns}
      data={data}
      id="used-storage-table"
      isLoading={false}
      noData="No disk or partition has been fully utilised."
      variant="regular"
    />
  );
};

export default UsedStorageTable;
