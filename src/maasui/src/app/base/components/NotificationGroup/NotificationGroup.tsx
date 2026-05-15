import { useState } from "react";

import {
  Button,
  Icon,
  Notification as NotificationBanner,
} from "@canonical/react-components";
import type { NotificationProps } from "@canonical/react-components";
import classNames from "classnames";
import pluralize from "pluralize";
import { useDispatch } from "react-redux";
import type { Dispatch } from "redux";

import NotificationGroupNotification from "./Notification";

import { notificationActions } from "@/app/store/notification";
import type { Notification as NotificationType } from "@/app/store/notification/types";
import { capitaliseFirst } from "@/app/utils";

const dismissAll = (notifications: NotificationType[], dispatch: Dispatch) => {
  notifications.forEach((notification) => {
    if (notification.dismissable) {
      dispatch(notificationActions.dismiss(notification.id));
    }
  });
};

type Props = {
  notifications: NotificationType[];
  severity: NotificationProps["severity"];
};

const NotificationGroup = ({
  notifications,
  severity,
}: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const [groupOpen, setGroupOpen] = useState(false);

  const notificationCount =
    severity === "information"
      ? `${notifications.length} Other messages`
      : `${notifications.length} ${pluralize(
          capitaliseFirst(notifications[0].category),
          notifications.length
        )}`;

  const dismissable = notifications.some(({ dismissable }) => dismissable);

  return (
    <div className="p-notification-group">
      <NotificationBanner
        className={classNames("p-notification-group__summary", {
          "is-open": groupOpen,
        })}
        severity={severity}
        title={
          <>
            <Button
              appearance="link"
              aria-label={`${notifications.length} ${severity}, click to open messages.`}
              className="u-no-margin--bottom"
              onClick={(evt: React.MouseEvent) => {
                evt.preventDefault();
                setGroupOpen(!groupOpen);
              }}
            >
              <span
                className="p-heading--5 u-nudge-left--small"
                data-testid="notification-count"
              >
                {notificationCount}
              </span>
              <Icon name={groupOpen ? "collapse" : "expand"} />
            </Button>
            {dismissable && (
              <Button
                appearance="link"
                className="u-no-margin--bottom"
                inline
                onClick={() => {
                  dismissAll(notifications, dispatch);
                }}
              >
                Dismiss all
              </Button>
            )}
          </>
        }
      />
      {groupOpen &&
        notifications.map(({ id }) => (
          <NotificationGroupNotification
            className="p-notification-group__notification"
            id={id}
            key={id}
            severity={severity}
          />
        ))}
    </div>
  );
};

export default NotificationGroup;
