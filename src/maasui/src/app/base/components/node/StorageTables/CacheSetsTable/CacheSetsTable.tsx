import type { ReactElement } from "react";

import { GenericTable } from "@canonical/maas-react-components";

import useCacheSetsColumns from "./useCacheSetsColumns/useCacheSetsColumns";

import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import type { Disk } from "@/app/store/types/node";
import { isCacheSet, nodeIsMachine } from "@/app/store/utils";

type CacheSetsTableProps = {
  canEditStorage: boolean;
  node: ControllerDetails | MachineDetails;
};

const CacheSetsTable = ({
  canEditStorage,
  node,
}: CacheSetsTableProps): ReactElement => {
  const isMachine = nodeIsMachine(node);

  const newRows = node.disks.reduce<Disk[]>((rows, disk) => {
    if (isCacheSet(disk)) {
      rows.push(disk);
    }
    return rows;
  }, []);

  const columns = useCacheSetsColumns({
    isMachine,
    canEditStorage,
    systemId: node.system_id,
  });

  return (
    <GenericTable
      columns={columns}
      data={newRows}
      isLoading={false}
      noData={"No cache sets available."}
      variant="regular"
    />
  );
};

export default CacheSetsTable;
