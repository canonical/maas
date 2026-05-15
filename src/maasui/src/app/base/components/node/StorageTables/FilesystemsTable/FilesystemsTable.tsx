import type { ReactElement } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { Button, Tooltip } from "@canonical/react-components";

import AddSpecialFilesystem from "@/app/base/components/node/StorageTables/FilesystemsTable/AddSpecialFilesystem";
import useFileSystemsTableColumns from "@/app/base/components/node/StorageTables/FilesystemsTable/useFilesystemsTableColumns/useFileSystemsTableColumns";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { ControllerDetails } from "@/app/store/controller/types";
import type { MachineDetails } from "@/app/store/machine/types";
import type { Disk, Partition } from "@/app/store/types/node";
import { isMounted, nodeIsMachine } from "@/app/store/utils";

type FilesystemsTableProps = {
  canEditStorage: boolean;
  node: ControllerDetails | MachineDetails;
};

export type FilesystemRow = {
  id: string;
  name?: string;
  size?: number;
  node: ControllerDetails | MachineDetails;
  storage?: Disk | Partition;
  fstype: string;
  is_format_fstype: boolean;
  label: string;
  mount_options: string | null;
  mount_point: string;
  used_for: string;
};

const generateFilesystemRowData = (
  node: ControllerDetails | MachineDetails
): FilesystemRow[] => {
  const data: FilesystemRow[] = [];

  const addFilesystem = (storage: Disk | Partition) => {
    if (!isMounted(storage.filesystem)) return;
    data.push({
      name: storage.name,
      size: storage.size,
      node,
      storage,
      ...storage.filesystem,
      id: `${storage.filesystem.fstype}-${storage.filesystem.id}`,
    });
  };

  node.disks.forEach((disk) => {
    addFilesystem(disk);

    if (disk.partitions) {
      disk.partitions.forEach((partition) => {
        addFilesystem(partition);
      });
    }
  });

  if (node.special_filesystems) {
    node.special_filesystems.forEach((specialFilesystem) => {
      data.push({
        node,
        ...specialFilesystem,
        id: `${specialFilesystem.fstype}-${specialFilesystem.id}`,
      });
    });
  }

  return data;
};

const FilesystemsTable = ({
  canEditStorage,
  node,
}: FilesystemsTableProps): ReactElement => {
  const isMachine = nodeIsMachine(node);
  const { openSidePanel } = useSidePanel();

  const columns = useFileSystemsTableColumns(canEditStorage, isMachine);
  const data = generateFilesystemRowData(node);

  return (
    <>
      <GenericTable
        columns={columns}
        data={data}
        isLoading={false}
        noData="No filesystems defined."
        sorting={[{ id: "name", desc: false }]}
        style={{ marginBottom: "1.5rem" }}
        variant="regular"
      />
      {canEditStorage && (
        <Tooltip message="Create a tmpfs or ramfs filesystem.">
          <Button
            data-testid="add-special-fs-button"
            onClick={() => {
              isMachine &&
                openSidePanel({
                  component: AddSpecialFilesystem,
                  title: "Add special filesystem",
                  props: { machine: node },
                });
            }}
          >
            Add special filesystem
          </Button>
        </Tooltip>
      )}
    </>
  );
};

export default FilesystemsTable;
