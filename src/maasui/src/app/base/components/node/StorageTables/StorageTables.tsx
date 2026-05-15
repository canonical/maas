import { Strip } from "@canonical/react-components";

import AvailableStorageTable from "./AvailableStorageTable";
import CacheSetsTable from "./CacheSetsTable";
import DatastoresTable from "./DatastoresTable";
import FilesystemsTable from "./FilesystemsTable";
import UsedStorageTable from "./UsedStorageTable";

import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import { isCacheSet, isVMWareLayout } from "@/app/store/utils";

export enum Labels {
  AvailableStorage = "Available disks and partitions",
  CacheSets = "Available cache sets",
  Datastores = "Datastores",
  Filesystems = "Filesystems",
  UsedStorage = "Used disks and partitions",
}

type Props = {
  canEditStorage: boolean;
  node: ControllerDetails | MachineDetails;
};

const StorageTables = ({ canEditStorage, node }: Props): React.ReactElement => {
  const showDatastores = isVMWareLayout(node.detected_storage_layout);
  const showCacheSets = node.disks.some((disk) => isCacheSet(disk));

  return (
    <>
      <Strip shallow>
        {showDatastores ? (
          <>
            <h4 className="u-sv-1">{Labels.Datastores}</h4>
            <DatastoresTable canEditStorage={canEditStorage} node={node} />
          </>
        ) : (
          <>
            <h4 className="u-sv-1">{Labels.Filesystems}</h4>
            <FilesystemsTable canEditStorage={canEditStorage} node={node} />
          </>
        )}
      </Strip>
      {showCacheSets && (
        <Strip shallow>
          <h4 className="u-sv-1">{Labels.CacheSets}</h4>
          <CacheSetsTable canEditStorage={canEditStorage} node={node} />
        </Strip>
      )}
      <Strip shallow>
        <h4 className="u-sv-1">{Labels.AvailableStorage}</h4>
        <AvailableStorageTable canEditStorage={canEditStorage} node={node} />
      </Strip>
      <Strip shallow>
        <h4 className="u-sv-1">{Labels.UsedStorage}</h4>
        <UsedStorageTable node={node} />
      </Strip>
    </>
  );
};

export default StorageTables;
