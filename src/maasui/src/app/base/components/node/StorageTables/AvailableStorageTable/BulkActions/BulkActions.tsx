import { Button, List, Tooltip } from "@canonical/react-components";
import { useSelector } from "react-redux";

import CreateDatastore from "@/app/base/components/node/StorageTables/AvailableStorageTable/BulkActions/CreateDatastore";
import CreateRaid from "@/app/base/components/node/StorageTables/AvailableStorageTable/BulkActions/CreateRaid";
import CreateVolumeGroup from "@/app/base/components/node/StorageTables/AvailableStorageTable/BulkActions/CreateVolumeGroup";
import UpdateDatastore from "@/app/base/components/node/StorageTables/AvailableStorageTable/BulkActions/UpdateDatastore";
import { useSidePanel } from "@/app/base/side-panel-context";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import type { Disk, Partition } from "@/app/store/types/node";
import {
  canCreateOrUpdateDatastore,
  canCreateRaid,
  canCreateVolumeGroup,
  isDatastore,
  isVMWareLayout,
} from "@/app/store/utils";

type Props = {
  selected: (Disk | Partition)[];
  systemId: Machine["system_id"];
};

const BulkActions = ({
  selected,
  systemId,
}: Props): React.ReactElement | null => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const { openSidePanel } = useSidePanel();

  if (!isMachineDetails(machine)) {
    return null;
  }

  if (isVMWareLayout(machine.detected_storage_layout)) {
    const hasDatastores = machine.disks.some((disk) =>
      isDatastore(disk.filesystem)
    );
    const createDatastoreEnabled = canCreateOrUpdateDatastore(selected);
    const updateDatastoreEnabled = createDatastoreEnabled && hasDatastores;

    let updateTooltip: string | null = null;
    if (!hasDatastores) {
      updateTooltip = "No datastores detected.";
    } else if (!updateDatastoreEnabled) {
      updateTooltip =
        "Select one or more unpartitioned and unformatted storage devices to add to an existing datastore.";
    }

    return (
      <List
        className="u-no-margin--bottom"
        data-testid="vmware-bulk-actions"
        inline
        items={[
          <Tooltip
            data-testid="create-datastore-tooltip"
            message={
              !createDatastoreEnabled
                ? "Select one or more unpartitioned and unformatted storage devices to create a datastore."
                : null
            }
            position="top-left"
          >
            <Button
              data-testid="create-datastore"
              disabled={!createDatastoreEnabled}
              onClick={() => {
                openSidePanel({
                  component: CreateDatastore,
                  title: "Create datastore",
                  props: { selected, systemId: systemId },
                });
              }}
            >
              Create datastore
            </Button>
          </Tooltip>,
          <Tooltip
            data-testid="add-to-datastore-tooltip"
            message={updateTooltip}
            position="top-left"
          >
            <Button
              data-testid="add-to-datastore"
              disabled={!updateDatastoreEnabled}
              onClick={() => {
                openSidePanel({
                  component: UpdateDatastore,
                  title: "Update datastore",
                  props: { selected, systemId: systemId },
                });
              }}
            >
              Add to existing datastore
            </Button>
          </Tooltip>,
        ]}
      />
    );
  }

  const createRaidEnabled = canCreateRaid(selected);
  const createVgEnabled = canCreateVolumeGroup(selected);

  return (
    <List
      className="u-no-margin--bottom"
      inline
      items={[
        <Tooltip
          data-testid="create-vg-tooltip"
          message={
            !createVgEnabled
              ? "Select one or more unpartitioned and unformatted storage devices to create a volume group."
              : null
          }
          position="top-left"
        >
          <Button
            data-testid="create-vg"
            disabled={!createVgEnabled}
            onClick={() => {
              openSidePanel({
                component: CreateVolumeGroup,
                title: "Create volume group",
                props: { selected, systemId: systemId },
              });
            }}
          >
            Create volume group
          </Button>
        </Tooltip>,
        <Tooltip
          data-testid="create-raid-tooltip"
          message={
            !createRaidEnabled
              ? "Select two or more unpartitioned and unmounted storage devices to create a RAID."
              : null
          }
          position="top-left"
        >
          <Button
            data-testid="create-raid"
            disabled={!createRaidEnabled}
            onClick={() => {
              openSidePanel({
                component: CreateRaid,
                title: "Create raid",
                props: { selected, systemId: systemId },
              });
            }}
          >
            Create RAID
          </Button>
        </Tooltip>,
      ]}
    />
  );
};

export default BulkActions;
