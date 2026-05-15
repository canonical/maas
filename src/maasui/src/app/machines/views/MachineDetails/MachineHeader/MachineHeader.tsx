import type { ReactElement } from "react";
import { useEffect, useState } from "react";

import { useDispatch, useSelector } from "react-redux";
import { Link, useLocation } from "react-router";

import MachineName from "./MachineName";

import PowerIcon from "@/app/base/components/PowerIcon";
import ScriptStatus from "@/app/base/components/ScriptStatus";
import SectionHeader from "@/app/base/components/SectionHeader";
import TooltipButton from "@/app/base/components/TooltipButton";
import MachineActions from "@/app/machines/components/MachineActions";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import { isUnconfiguredPowerType } from "@/app/store/machine/utils/common";
import { useFetchMachine } from "@/app/store/machine/utils/hooks";
import type { RootState } from "@/app/store/root/types";
import { ScriptResultStatus } from "@/app/store/scriptresult/types";
import { NodeActions } from "@/app/store/types/node";
import { canOpenActionForm } from "@/app/store/utils";

type MachineHeaderProps = {
  systemId: Machine["system_id"];
};

const MachineHeader = ({ systemId }: MachineHeaderProps): ReactElement => {
  const dispatch = useDispatch();
  const [editingName, setEditingName] = useState(false);
  const { pathname } = useLocation();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const statuses = useSelector((state: RootState) =>
    machineSelectors.getStatuses(state, systemId)
  );
  const isDetails = isMachineDetails(machine);
  const selected = useSelector(machineSelectors.selected);
  useFetchMachine(systemId);

  useEffect(() => {
    if (machine) {
      if (
        (selected &&
          "items" in selected &&
          !selected.items?.some(
            (selectedMachine) => selectedMachine === machine.system_id
          )) ||
        (selected && !("items" in selected)) ||
        !selected
      )
        dispatch(machineActions.setSelected({ items: [machine.system_id] }));
    }
  }, [dispatch, machine, machine?.system_id, selected]);

  if (!(machine && isDetails)) {
    return <SectionHeader loading />;
  }

  const urlBase = `/machine/${systemId}`;
  const checkingPower = statuses?.checkingPower;
  const needsPowerConfiguration = isUnconfiguredPowerType(machine);

  const disabledActions = [
    NodeActions.ACQUIRE,
    NodeActions.COMMISSION,
    NodeActions.DEPLOY,
    NodeActions.CLONE,
    NodeActions.RELEASE,
    NodeActions.ABORT,
  ].filter((action) => !canOpenActionForm(machine, action));

  return (
    <SectionHeader
      renderButtons={() => (
        <MachineActions
          disabledActions={disabledActions}
          isViewingDetails
          systemId={machine.system_id}
        />
      )}
      subtitle={
        editingName ? null : (
          <div className="u-flex--wrap u-flex--align-center">
            <div className="u-nudge-left">
              {machine.locked ? (
                <TooltipButton
                  aria-label="locked"
                  className="u-nudge-left--small"
                  iconName="locked"
                  message="This machine is locked. You have to unlock it to perform any actions."
                  position="btm-left"
                />
              ) : null}
              {machine.status}
            </div>
            <div>
              <PowerIcon
                data-testid="machine-header-power"
                powerState={machine.power_state}
                showSpinner={checkingPower}
              >
                {checkingPower
                  ? "Checking power"
                  : `Powered ${machine.power_state}`}
              </PowerIcon>
            </div>
          </div>
        )
      }
      subtitleLoading={!isMachineDetails(machine)}
      tabLinks={[
        {
          active: pathname.startsWith(`${urlBase}/summary`),
          component: Link,
          label: "Summary",
          to: `${urlBase}/summary`,
        },
        ...(isDetails && machine.devices?.length >= 1
          ? [
              {
                active: pathname.startsWith(`${urlBase}/instances`),
                component: Link,
                label: "Instances",
                to: `${urlBase}/instances`,
              },
            ]
          : []),
        {
          active: pathname.startsWith(`${urlBase}/network`),
          component: Link,
          label: "Network",
          to: `${urlBase}/network`,
        },
        {
          active: pathname.startsWith(`${urlBase}/storage`),
          component: Link,
          label: "Storage",
          to: `${urlBase}/storage`,
        },
        {
          active: pathname.startsWith(`${urlBase}/pci-devices`),
          component: Link,
          label: "PCI devices",
          to: `${urlBase}/pci-devices`,
        },
        {
          active: pathname.startsWith(`${urlBase}/usb-devices`),
          component: Link,
          label: "USB",
          to: `${urlBase}/usb-devices`,
        },
        {
          active: pathname.startsWith(`${urlBase}/scripts`),
          component: Link,
          label: "Scripts",
          to: `${urlBase}/scripts`,
        },
        {
          active: pathname.startsWith(`${urlBase}/logs`),
          component: Link,
          label: (
            <ScriptStatus status={machine.installation_status}>
              Logs
            </ScriptStatus>
          ),
          to: `${urlBase}/logs`,
        },
        {
          active: pathname.startsWith(`${urlBase}/configuration`),
          component: Link,
          label: (
            <ScriptStatus
              status={
                needsPowerConfiguration
                  ? ScriptResultStatus.FAILED
                  : ScriptResultStatus.NONE
              }
            >
              Configuration
            </ScriptStatus>
          ),
          to: `${urlBase}/configuration`,
        },
      ]}
      title={
        <MachineName
          editingName={editingName}
          id={systemId}
          setEditingName={setEditingName}
        />
      }
      titleElement={editingName ? "div" : "h1"}
    />
  );
};

export default MachineHeader;
