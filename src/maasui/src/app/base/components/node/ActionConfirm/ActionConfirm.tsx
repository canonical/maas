import type { ReactNode } from "react";

import {
  ActionButton,
  Button,
  Col,
  Notification as NotificationBanner,
  Row,
} from "@canonical/react-components";
import type { ActionButtonProps } from "@canonical/react-components";

import { useSendAnalyticsWhen } from "@/app/base/hooks";
import type { AnalyticsEvent } from "@/app/base/types";
import { useMachineDetailsForm } from "@/app/machines/hooks";
import type { Machine, MachineStatus } from "@/app/store/machine/types";
import { formatErrors } from "@/app/utils";

type Props = {
  confirmLabel: string;
  eventName?: string;
  message?: ReactNode;
  closeExpanded: () => void;
  onConfirm: () => void;
  onSaveAnalytics: AnalyticsEvent;
  statusKey: keyof MachineStatus;
  submitAppearance?: ActionButtonProps["appearance"];
  systemId: Machine["system_id"];
};

const ActionConfirm = ({
  closeExpanded,
  confirmLabel,
  eventName,
  message,
  onConfirm,
  onSaveAnalytics,
  statusKey,
  submitAppearance = "negative",
  systemId,
}: Props): React.ReactElement => {
  const { errors, saved, saving } = useMachineDetailsForm(
    systemId,
    statusKey,
    eventName,
    () => {
      closeExpanded();
    }
  );
  const formattedErrors = formatErrors(errors);

  useSendAnalyticsWhen(
    saved,
    onSaveAnalytics.category,
    onSaveAnalytics.action,
    onSaveAnalytics.label
  );

  return (
    <Row>
      {formattedErrors ? (
        <NotificationBanner severity="negative">
          <span data-testid="error-message">{formattedErrors}</span>
        </NotificationBanner>
      ) : null}
      <Col size={8}>
        {message && (
          <p className="u-no-margin--bottom u-no-max-width">
            <i className="p-icon--warning is-inline">Warning</i>
            {message}
          </p>
        )}
      </Col>
      <Col className="u-align--right" size={4}>
        <Button className="u-no-margin--bottom" onClick={closeExpanded}>
          Cancel
        </Button>
        <ActionButton
          appearance={submitAppearance}
          className="u-no-margin--bottom"
          loading={saving}
          onClick={onConfirm}
        >
          {confirmLabel}
        </ActionButton>
      </Col>
    </Row>
  );
};

export default ActionConfirm;
