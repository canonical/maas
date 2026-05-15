import { NotificationSeverity } from "@canonical/react-components";
import { useSelector } from "react-redux";

import { useCanEdit } from "@/app/base/hooks";
import { useGetURLId } from "@/app/base/hooks/urls";
import MachineNotifications from "@/app/machines/views/MachineDetails/MachineNotifications";
import machineSelectors from "@/app/store/machine/selectors";
import { MachineMeta } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import {
  canOsSupportBcacheZFS,
  canOsSupportStorageConfig,
  isNodeStorageConfigurable,
} from "@/app/store/utils";

const StorageNotifications = (): React.ReactElement | null => {
  const id = useGetURLId(MachineMeta.PK);
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );
  const canEdit = useCanEdit(machine, true);
  const machineStorageConfigurable = isNodeStorageConfigurable(machine);

  if (!isMachineDetails(machine)) {
    return null;
  }

  const osSupportsStorageConfig = canOsSupportStorageConfig(machine);
  const osSupportsBcacheZFS = canOsSupportBcacheZFS(machine);

  // If the machine has not been commissioned just show the one notification.
  // Otherwise show all that are relevant.
  const notifications =
    machine.disks.length === 0
      ? [
          {
            active: true,
            content:
              "No storage information. Commission this machine to gather storage information.",
            severity: NotificationSeverity.NEGATIVE,
            title: "Error:",
          },
        ]
      : [
          {
            active: canEdit && !machineStorageConfigurable,
            content:
              "Storage configuration cannot be modified unless the machine is Ready.",
          },
          {
            active: canEdit && !osSupportsStorageConfig,
            content:
              "Custom storage configuration is only supported on Ubuntu, CentOS, and RHEL.",
          },
          {
            active: canEdit && !osSupportsBcacheZFS,
            content: "Bcache and ZFS are only supported on Ubuntu.",
          },
          ...(machine.storage_layout_issues?.length > 0
            ? machine.storage_layout_issues.map((issue) => ({
                active: true,
                content: `${issue}`,
                severity: NotificationSeverity.NEGATIVE,
                title: "Error:",
              }))
            : []),
        ];

  return <MachineNotifications notifications={notifications} />;
};

export default StorageNotifications;
