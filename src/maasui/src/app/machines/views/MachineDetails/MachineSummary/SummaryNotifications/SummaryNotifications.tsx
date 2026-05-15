import { useSelector } from "react-redux";
import { Link } from "react-router";

import {
  useFetchActions,
  useCanEdit,
  useIsRackControllerConnected,
} from "@/app/base/hooks";
import { useGetURLId } from "@/app/base/hooks/urls";
import urls from "@/app/base/urls";
import MachineNotifications from "@/app/machines/views/MachineDetails/MachineNotifications";
import { generalActions } from "@/app/store/general";
import { architectures as architecturesSelectors } from "@/app/store/general/selectors";
import machineSelectors from "@/app/store/machine/selectors";
import { MachineMeta } from "@/app/store/machine/types";
import {
  isMachineDetails,
  useHasInvalidArchitecture,
} from "@/app/store/machine/utils";
import {
  getHasSyncFailed,
  isDeployedWithHardwareSync,
} from "@/app/store/machine/utils/common";
import type { RootState } from "@/app/store/root/types";
import { PowerState } from "@/app/store/types/enum";
import type { NodeEvent } from "@/app/store/types/node";
import { isId } from "@/app/utils";

const formatEventText = (event: NodeEvent) => {
  if (!event) {
    return "";
  }
  const text = [];
  if (event.type?.description) {
    text.push(event.type.description);
  }
  if (event.description) {
    text.push(event.description);
  }
  return text.join(" - ");
};

const SummaryNotifications = (): React.ReactElement | null => {
  const id = useGetURLId(MachineMeta.PK);
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );
  const architectures = useSelector(architecturesSelectors.get);
  const architecturesLoaded = useSelector(architecturesSelectors.loaded);
  const hasUsableArchitectures = architectures.length > 0;
  const canEdit = useCanEdit(machine, true);
  const isRackControllerConnected = useIsRackControllerConnected();
  const hasInvalidArchitecture = useHasInvalidArchitecture(machine);
  const hasSyncFailed =
    isDeployedWithHardwareSync(machine) && getHasSyncFailed(machine);

  useFetchActions([generalActions.fetchArchitectures]);

  // Confirm that the full machine details have been fetched. This also allows
  // TypeScript know we're using the right union type (otherwise it will
  // complain that events don't exist on the base machine type).
  if (!isMachineDetails(machine) || !architecturesLoaded || !isId(id)) {
    return null;
  }

  return (
    <MachineNotifications
      notifications={[
        {
          active:
            machine.power_state === PowerState.ERROR &&
            machine.events?.length > 0,
          content: (
            <>
              {formatEventText(machine.events[0])}.{" "}
              <Link
                className="p-notification__action"
                to={urls.machines.machine.logs.index({ id: machine.system_id })}
              >
                See logs
              </Link>
            </>
          ),
          severity: "negative",
          title: "Error:",
        },
        {
          active: canEdit && !isRackControllerConnected,
          content:
            "Editing is currently disabled because no rack controller is currently connected to the region.",
          severity: "negative",
          title: "Error:",
        },
        {
          active:
            canEdit &&
            hasInvalidArchitecture &&
            isRackControllerConnected &&
            hasUsableArchitectures,
          content:
            "This machine currently has an invalid architecture. Update the architecture of this machine to make it deployable.",
          severity: "negative",
          title: "Error:",
        },
        {
          active:
            canEdit &&
            hasInvalidArchitecture &&
            isRackControllerConnected &&
            !hasUsableArchitectures,
          content: (
            <>
              No boot images have been imported for a valid architecture to be
              selected. Visit the{" "}
              <Link to={urls.images.index}>images page</Link> to start the
              import process.
            </>
          ),
          severity: "negative",
          title: "Error:",
        },
        {
          active: machine.cpu_count === 0,
          content:
            "Commission this machine to get CPU, Memory and Storage information.",
        },
        {
          active: hasSyncFailed,
          content: (
            <>
              This machine was not synced when it was scheduled. Check the{" "}
              <Link to={urls.machines.machine.logs.index({ id })}>
                machine logs
              </Link>{" "}
              for more information.
            </>
          ),
          severity: "caution",
        },
      ]}
    />
  );
};

export default SummaryNotifications;
