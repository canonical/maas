import { Button, Icon, Switch } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import DeleteMachine from "../MachineForms/DeleteMachine/DeleteMachine";
import CloneForm from "../MachineForms/MachineActionFormWrapper/CloneForm";
import CommissionForm from "../MachineForms/MachineActionFormWrapper/CommissionForm";
import DeployForm from "../MachineForms/MachineActionFormWrapper/DeployForm";
import MarkBrokenForm from "../MachineForms/MachineActionFormWrapper/MarkBrokenForm";
import OverrideTestForm from "../MachineForms/MachineActionFormWrapper/OverrideTestForm";
import ReleaseForm from "../MachineForms/MachineActionFormWrapper/ReleaseForm";
import SetMachineZoneForm from "../MachineForms/MachineActionFormWrapper/SetMachineZoneForm/SetMachineZoneForm";
import SetPoolForm from "../MachineForms/MachineActionFormWrapper/SetPoolForm";
import TagForm from "../MachineForms/MachineActionFormWrapper/TagForm";
import TestMachineForm from "../MachineForms/MachineActionFormWrapper/TestMachineForm";

import type { MachineActionGroup } from "./types";

import FieldlessForm from "@/app/base/components/node/FieldlessForm";
import PowerOffForm from "@/app/base/components/node/PowerOffForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import { useSelectedMachinesActionsDispatch } from "@/app/store/machine/utils/hooks";
import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import { canOpenActionForm } from "@/app/store/utils";

export const useMachineActionMenus = (
  isViewingDetails: boolean,
  systemId?: Machine["system_id"]
) => {
  const { openSidePanel } = useSidePanel();
  const dispatch = useDispatch();

  const selectedMachines = useSelector(machineSelectors.selected);
  const searchFilter = FilterMachines.filtersToString(
    FilterMachines.queryStringToFilters(location.search)
  );

  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );

  const { actionErrors } = useSelectedMachinesActionsDispatch({
    selectedMachines,
    searchFilter,
  });

  const actionMenus: MachineActionGroup[] = [
    {
      name: "lifecycle",
      items: [
        {
          action: NodeActions.COMMISSION,
          label: "Commission",
          onClick: () => {
            openSidePanel({
              component: CommissionForm,
              title: "Commission",
              props: {
                isViewingDetails,
              },
            });
          },
        },
        {
          action: NodeActions.ACQUIRE,
          label: "Allocate",
          onClick: () => {
            openSidePanel({
              component: FieldlessForm,
              title: "Allocate",
              props: {
                action: NodeActions.ACQUIRE,
                actions: machineActions,
                cleanup: machineActions.cleanup,
                errors: actionErrors,
                modelName: "machine",
                viewingDetails: isViewingDetails,
              },
            });
          },
        },
        {
          action: NodeActions.DEPLOY,
          label: "Deploy",
          onClick: () => {
            openSidePanel({
              component: DeployForm,
              props: {
                isViewingDetails,
              },
              title: "Deploy",
            });
          },
        },
        {
          action: NodeActions.RELEASE,
          label: "Release",
          onClick: () => {
            openSidePanel({
              component: ReleaseForm,
              props: {
                isViewingDetails,
              },
              title: "Release",
            });
          },
        },
        {
          action: NodeActions.ABORT,
          label: "Abort",
          onClick: () => {
            openSidePanel({
              component: FieldlessForm,
              title: "Abort",
              props: {
                action: NodeActions.ABORT,
                actions: machineActions,
                cleanup: machineActions.cleanup,
                errors: actionErrors,
                modelName: "machine",
                viewingDetails: isViewingDetails,
              },
            });
          },
        },
        {
          action: NodeActions.CLONE,
          label: "Clone from",
          onClick: () => {
            openSidePanel({
              component: CloneForm,
              props: {
                isViewingDetails,
              },
              title: "Clone from",
            });
          },
        },
      ],
      title: "Actions",
    },
    {
      name: "power",
      items: [
        {
          action: NodeActions.ON,
          label: "Power on",
          onClick: () => {
            openSidePanel({
              component: FieldlessForm,
              title: "Power on",
              props: {
                action: NodeActions.ON,
                actions: machineActions,
                cleanup: machineActions.cleanup,
                errors: actionErrors,
                modelName: "machine",
                viewingDetails: isViewingDetails,
              },
            });
          },
        },
        {
          action: NodeActions.OFF,
          label: "Power off",
          onClick: () => {
            openSidePanel({
              component: PowerOffForm,
              title: "Power off",
              props: {
                action: NodeActions.OFF,
                actions: machineActions,
                cleanup: machineActions.cleanup,
                errors: actionErrors,
                modelName: "machine",
                viewingDetails: isViewingDetails,
              },
            });
          },
        },
        ...(import.meta.env.VITE_APP_DPU_PROVISIONING === "true"
          ? [
              {
                action: NodeActions.POWER_CYCLE,
                label: "Power cycle",
                onClick: () => {
                  openSidePanel({
                    component: FieldlessForm,
                    title: "Power cycle",
                    props: {
                      action: NodeActions.POWER_CYCLE,
                      actions: machineActions,
                      cleanup: machineActions.cleanup,
                      errors: actionErrors,
                      modelName: "machine",
                      viewingDetails: isViewingDetails,
                    },
                  });
                },
              },
            ]
          : []),
        {
          action: NodeActions.SOFT_OFF,
          label: "Soft power off",
          onClick: () => {
            openSidePanel({
              component: PowerOffForm,
              title: "Soft power off",
              props: {
                action: NodeActions.SOFT_OFF,
                actions: machineActions,
                cleanup: machineActions.cleanup,
                errors: actionErrors,
                modelName: "machine",
                viewingDetails: isViewingDetails,
              },
            });
          },
        },
        ...(isViewingDetails && systemId
          ? [
              {
                action: NodeActions.CHECK_POWER,
                label: "Check power",
                onClick: () => dispatch(machineActions.checkPower(systemId)),
              },
            ]
          : []),
      ],
      title: "Power",
    },
    {
      name: "testing",
      items: [
        {
          action: NodeActions.TEST,
          label: "Test",
          onClick: () => {
            openSidePanel({
              component: TestMachineForm,
              props: {
                isViewingDetails,
              },
              title: "Test",
            });
          },
        },
        {
          action: NodeActions.RESCUE_MODE,
          label: "Enter rescue mode",
          onClick: () => {
            openSidePanel({
              component: FieldlessForm,
              props: {
                action: NodeActions.RESCUE_MODE,
                actions: machineActions,
                cleanup: machineActions.cleanup,
                errors: actionErrors,
                modelName: "machine",
                viewingDetails: isViewingDetails,
              },
              title: "Enter rescue mode",
            });
          },
        },
        {
          action: NodeActions.EXIT_RESCUE_MODE,
          label: "Exit rescue mode",
          onClick: () => {
            openSidePanel({
              component: FieldlessForm,
              props: {
                action: NodeActions.EXIT_RESCUE_MODE,
                actions: machineActions,
                cleanup: machineActions.cleanup,
                errors: actionErrors,
                modelName: "machine",
                viewingDetails: isViewingDetails,
              },
              title: "Exit rescue mode",
            });
          },
        },
        {
          action: NodeActions.MARK_FIXED,
          label: "Mark fixed",
          onClick: () => {
            openSidePanel({
              component: FieldlessForm,
              props: {
                action: NodeActions.MARK_FIXED,
                actions: machineActions,
                cleanup: machineActions.cleanup,
                errors: actionErrors,
                modelName: "machine",
                viewingDetails: isViewingDetails,
              },
              title: "Mark fixed",
            });
          },
        },
        {
          action: NodeActions.MARK_BROKEN,
          label: "Mark broken",
          onClick: () => {
            openSidePanel({
              component: MarkBrokenForm,
              props: {
                isViewingDetails,
              },
              title: "Mark broken",
            });
          },
        },
        {
          action: NodeActions.OVERRIDE_FAILED_TESTING,
          label: "Override failed testing",
          onClick: () => {
            openSidePanel({
              component: OverrideTestForm,
              props: {
                isViewingDetails,
              },
              title: "Override failed testing",
            });
          },
        },
      ],
      title: "Troubleshoot",
    },
    {
      name: "misc",
      items: [
        {
          action: NodeActions.TAG,
          label: "Tag",
          onClick: () => {
            openSidePanel({
              component: TagForm,
              props: {
                isViewingDetails,
              },
              title: "Tag",
            });
          },
        },
        {
          action: NodeActions.SET_ZONE,
          label: "Set zone",
          onClick: () => {
            openSidePanel({
              component: SetMachineZoneForm,
              props: {
                isViewingDetails,
              },
              title: "Set zone",
            });
          },
        },
        {
          action: NodeActions.SET_POOL,
          label: "Set pool",
          onClick: () => {
            openSidePanel({
              component: SetPoolForm,
              props: {
                isViewingDetails,
              },
              title: "Set pool",
            });
          },
        },
      ],
      title: "Categorise",
    },
    {
      name: "lock",
      items: [
        {
          action: NodeActions.LOCK,
          label: "Lock",
          onClick: () => {
            openSidePanel({
              component: FieldlessForm,
              props: {
                action: NodeActions.LOCK,
                actions: machineActions,
                cleanup: machineActions.cleanup,
                errors: actionErrors,
                modelName: "machine",
                viewingDetails: isViewingDetails,
              },
              title: "Lock",
            });
          },
        },
        {
          action: NodeActions.UNLOCK,
          label: "Unlock",
          onClick: () => {
            openSidePanel({
              component: FieldlessForm,
              props: {
                action: NodeActions.UNLOCK,
                actions: machineActions,
                cleanup: machineActions.cleanup,
                errors: actionErrors,
                modelName: "machine",
                viewingDetails: isViewingDetails,
              },
              title: "Unlock",
            });
          },
        },
      ],
      render:
        isViewingDetails && machine
          ? () => {
              if (
                canOpenActionForm(machine, NodeActions.LOCK) ||
                canOpenActionForm(machine, NodeActions.UNLOCK)
              ) {
                return (
                  <Switch
                    checked={machine.locked}
                    label="Lock"
                    onChange={() =>
                      dispatch(
                        machine.locked
                          ? machineActions.unlock({
                              system_id: machine.system_id,
                            })
                          : machineActions.lock({
                              system_id: machine.system_id,
                            })
                      )
                    }
                  />
                );
              } else {
                return <></>;
              }
            }
          : undefined,
      title: "Lock",
    },
    {
      name: "delete",
      items: [
        {
          action: NodeActions.DELETE,
          label: "Delete",
          onClick: () => {
            openSidePanel({
              component: DeleteMachine,
              props: {
                isViewingDetails,
              },
              title: "Delete",
            });
          },
        },
      ],
      render: () => (
        <Button
          onClick={() => {
            openSidePanel({
              component: DeleteMachine,
              props: {
                isViewingDetails,
              },
              title: "Delete",
            });
          }}
        >
          <Icon name="delete" />
          Delete
        </Button>
      ),
      icon: "delete",
      title: "Delete",
    },
  ];

  return actionMenus;
};
