import { useCallback, useEffect } from "react";

import { usePrevious } from "@canonical/react-components/dist/hooks";
import { useSelector } from "react-redux";

import machineSelectors from "@/app/store/machine/selectors";
import type {
  Machine,
  MachineState,
  MachineStatus,
} from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";

/**
 * Create a callback for toggling the menu
 * @param onToggleMenu - The function to toggle the menu.
 * @param systemId - The machine id.
 * @returns The toggle callback.
 */
export const useToggleMenu = (
  onToggleMenu: ((open: boolean) => void) | null
): ((open: boolean) => void) => {
  return useCallback(
    (open) => {
      if (onToggleMenu) {
        onToggleMenu(open);
      }
    },
    [onToggleMenu]
  );
};

/**
 * Get the error, saved and saving state for a single machine performing a
 * single action.
 * @param systemId - system_id of the machine to check.
 * @param statusName - name of the relevant machine status e.g. "updatingDisk".
 * @param eventName - name of the machine event to filter errors by e.g. "updateDisk".
 * @param onSaved - function to execute when form successfully saved.
 * @returns object with errors, saved and saving state for machine performing
 * the action
 */
export const useMachineDetailsForm = (
  systemId: Machine["system_id"],
  statusKey: keyof MachineStatus,
  eventName?: string,
  onSaved?: () => void
): {
  errors: MachineState["eventErrors"][0]["error"];
  saved: boolean;
  saving: boolean;
} => {
  const statuses = useSelector((state: RootState) =>
    machineSelectors.getStatuses(state, systemId)
  );
  const errors = useSelector((state: RootState) =>
    machineSelectors.eventErrorsForIds(state, systemId, eventName)
  );
  const saving = statuses[statusKey];
  const previousSaving = usePrevious(saving);
  const saved = !saving && previousSaving && errors.length === 0;

  useEffect(() => {
    if (onSaved && saved) {
      onSaved();
    }
  }, [onSaved, saved]);

  return { errors: errors[0]?.error, saved, saving };
};
