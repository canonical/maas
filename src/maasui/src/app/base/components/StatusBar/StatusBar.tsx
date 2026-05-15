import { useEffect, type ReactNode } from "react";

import {
  AppStatus,
  Button,
  Icon,
  ICONS,
  Link,
  useToastNotification,
} from "@canonical/react-components";
import {
  iconLookup,
  severityOrder,
} from "@canonical/react-components/dist/components/Notifications/ToastNotification/ToastNotificationList";
import classNames from "classnames";
import { useSelector } from "react-redux";

import TooltipButton from "../TooltipButton";

import { useNotifications } from "@/app/api/query/notifications";
import { useFetchActions, useUsabilla } from "@/app/base/hooks";
import configSelectors from "@/app/store/config/selectors";
import controllerSelectors from "@/app/store/controller/selectors";
import {
  isControllerDetails,
  isRack,
  isRegionAndRack,
} from "@/app/store/controller/utils";
import { generalActions } from "@/app/store/general";
import {
  installType as installTypeSelectors,
  version as versionSelectors,
} from "@/app/store/general/selectors";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineDetails } from "@/app/store/machine/types";
import {
  isDeployedWithHardwareSync,
  isMachineDetails,
} from "@/app/store/machine/utils";
import { msmActions } from "@/app/store/msm";
import msmSelectors from "@/app/store/msm/selectors";
import type { UtcDatetime } from "@/app/store/types/model";
import { NodeStatus } from "@/app/store/types/node";
import { formatUtcDatetime, getTimeDistanceString } from "@/app/utils/time";

const getLastCommissionedString = (machine: MachineDetails): string => {
  if (machine.status === NodeStatus.COMMISSIONING) {
    return "Commissioning in progress...";
  }

  const lastCommissioningTime = findLastCommissioningTime(machine);

  if (!lastCommissioningTime) {
    return "Not yet commissioned";
  }

  return formatLastCommissionedTime(lastCommissioningTime);
};

const findLastCommissioningTime = (
  machine: MachineDetails
): UtcDatetime | null => {
  const commissioningEvents = machine.events.filter(
    (event) => event.type.description === NodeStatus.COMMISSIONING
  );

  if (commissioningEvents.length > 0) {
    return commissioningEvents.reduce((latest, event) =>
      new Date(event.created) > new Date(latest.created) ? event : latest
    ).created;
  }

  return machine.commissioning_start_time &&
    machine.commissioning_start_time !== ""
    ? machine.commissioning_start_time
    : null;
};

function useEventListener<K extends keyof WindowEventMap>(
  type: K,
  listener: (event: WindowEventMap[K]) => void
) {
  useEffect(() => {
    window.addEventListener(type, listener);
    return () => {
      window.removeEventListener(type, listener);
    };
  }, [type, listener]);
}
const formatLastCommissionedTime = (
  lastCommissioningTime: UtcDatetime
): string => {
  try {
    const distance = getTimeDistanceString(lastCommissioningTime);
    return `Last commissioned: ${distance}`;
  } catch (error) {
    return `Unable to parse commissioning timestamp (${
      error instanceof Error ? error.message : error
    })`;
  }
};

const getSyncStatusString = (syncStatus: UtcDatetime) => {
  if (syncStatus === "") {
    return "Never";
  }
  try {
    return getTimeDistanceString(syncStatus);
  } catch (error) {
    return `Unable to parse sync timestamp (${
      error instanceof Error ? error.message : error
    })`;
  }
};

export const StatusBar = (): React.ReactElement | null => {
  const activeController = useSelector(controllerSelectors.active);
  const activeMachine = useSelector(machineSelectors.active);
  const version = useSelector(versionSelectors.get);
  const maasName = useSelector(configSelectors.maasName);
  const allowUsabilla = useUsabilla();
  const msmRunning = useSelector(msmSelectors.running);
  const installType = useSelector(installTypeSelectors.get);
  const { toggleListView, notifications, countBySeverity, isListView } =
    useToastNotification();

  useNotifications();
  useEventListener("keydown", (e: KeyboardEvent) => {
    // Close notifications list if Escape pressed
    if (e.code === "Escape" && isListView) {
      toggleListView();
    }
  });
  const notificationIcons = severityOrder.map((severity) => {
    if (countBySeverity[severity]) {
      return (
        <Icon
          aria-label={`${severity} notification exists`}
          key={severity}
          name={iconLookup[severity]}
        />
      );
    }
    return null;
  });

  const hasNotifications = notifications.length > 0;

  useFetchActions([msmActions.fetch, generalActions.fetchInstallType]);

  if (!(maasName && version)) {
    return null;
  }

  let status: ReactNode;
  if (isMachineDetails(activeMachine)) {
    const statuses = [activeMachine.fqdn];
    if (isDeployedWithHardwareSync(activeMachine)) {
      statuses.push(
        `Last synced: ${getSyncStatusString(activeMachine.last_sync)}`
      );
      statuses.push(
        `Next sync: ${getSyncStatusString(activeMachine.next_sync)}`
      );
    } else {
      statuses.push(getLastCommissionedString(activeMachine));
    }
    status = (
      <ul className="p-inline-list u-flex--wrap u-no-margin--bottom">
        {statuses.map((status, i) => (
          <li className="p-inline-list__item" key={status}>
            {i === 0 ? <strong>{status}</strong> : status}
          </li>
        ))}
      </ul>
    );
  } else if (
    isControllerDetails(activeController) &&
    (isRack(activeController) || isRegionAndRack(activeController))
  ) {
    status = `Last image sync: ${formatUtcDatetime(
      activeController.last_image_sync
    )}`;
  }

  return (
    <AppStatus aria-label="status bar" className="p-status-bar">
      <div className="p-status-bar__row u-flex">
        <div className="p-status-bar__primary u-flex--no-shrink u-flex--wrap">
          <strong data-testid="status-bar-maas-name">{maasName} MAAS</strong>
          :&nbsp;
          <span data-testid="status-bar-version">
            {version} ({installType})
          </span>
        </div>
        <div className="p-status-bar__primary u-flex--no-shrink u-flex--wrap">
          <span data-testid="status-bar-msm-status">
            {msmRunning === "connected" ? (
              <TooltipButton
                message="This MAAS is connected to a MAAS Site Manager.
It will regularly report to the Site Manager and choose
Site Manager as its upstream image source."
              >
                <Icon name="connected" />
                Connected to MAAS Site Manager
              </TooltipButton>
            ) : null}
          </span>
        </div>
        <ul className="p-inline-list--middot u-no-margin--bottom">
          <li className="p-inline-list__item">
            <Link
              href={`${import.meta.env.VITE_APP_BASENAME}/docs/`}
              rel="noreferrer"
              target="_blank"
            >
              Local documentation
            </Link>
          </li>
          <li className="p-inline-list__item">
            <Link
              href="https://www.ubuntu.com/legal"
              rel="noreferrer"
              target="_blank"
            >
              Legal information
            </Link>
          </li>
          {allowUsabilla ? (
            <li className="p-inline-list__item">
              <Button
                appearance="link"
                className="u-no-margin u-no-padding"
                onClick={() => {
                  window.usabilla_live("click");
                }}
              >
                Give feedback
              </Button>
            </li>
          ) : null}
        </ul>
        {status && (
          <div
            className="p-status-bar__secondary u-flex--grow u-flex--wrap"
            data-testid="status-bar-status"
          >
            {status}
          </div>
        )}
      </div>
      {hasNotifications && (
        <Button
          aria-label="Expand notifications list"
          className={classNames("u-no-margin expand-button", {
            "button-active": isListView,
          })}
          onClick={toggleListView}
        >
          {notificationIcons}
          <span className="total-count">{notifications.length}</span>
          <Icon name={isListView ? ICONS.chevronDown : ICONS.chevronUp} />
        </Button>
      )}
    </AppStatus>
  );
};

export default StatusBar;
