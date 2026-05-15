import type { ReactNode } from "react";

import { ActionButton, Button, Tooltip } from "@canonical/react-components";
import type { ActionButtonProps } from "@canonical/react-components";
import classNames from "classnames";
import type { FormikContextType } from "formik";
import { useFormikContext } from "formik";

export type FormikContextFunc<V, R = void> = (
  values: V,
  formikContext: FormikContextType<V>
) => R;

export type Props<V> = {
  buttonsClassName?: string;
  buttonsHelp?: ReactNode;
  buttonsHelpClassName?: string;
  cancelDisabled?: boolean;
  cancelLabel?: string;
  inline?: boolean;
  onCancel?: FormikContextFunc<V> | null;
  saved?: boolean;
  saving?: boolean;
  savingLabel?: string | null;
  secondarySubmit?: FormikContextFunc<V> | null;
  secondarySubmitSaved?: boolean;
  secondarySubmitSaving?: boolean;
  secondarySubmitDisabled?: boolean;
  secondarySubmitLabel?: FormikContextFunc<V, string> | string | null;
  secondarySubmitTooltip?: string | null;
  submitAppearance?: ActionButtonProps["appearance"];
  submitDisabled?: boolean;
  submitLabel?: string;
  /**
   * Determines the behavior of the primary and secondary submit buttons.
   * - "coupled" (default): The secondary submit button is disabled if the primary submit button is disabled.
   * - "independent": The secondary submit button's disabled state is controlled independently.
   */
  buttonsBehavior?: "coupled" | "independent";
};

export enum TestIds {
  ButtonsHelp = "buttons-help",
  ButtonsWrapper = "buttons-wrapper",
  CancelButton = "cancel-action",
  SavingLabel = "saving-label",
  SecondarySubmit = "secondary-submit",
}

export enum Labels {
  Cancel = "Cancel",
  Submit = "Save",
}

export const FormikFormButtons = <V,>({
  buttonsClassName,
  buttonsHelp,
  buttonsHelpClassName,
  cancelDisabled,
  cancelLabel = "Cancel",
  inline,
  onCancel,
  saved,
  saving,
  savingLabel,
  secondarySubmit,
  secondarySubmitSaved,
  secondarySubmitSaving,
  secondarySubmitDisabled,
  secondarySubmitLabel,
  secondarySubmitTooltip,
  submitAppearance = "positive",
  submitDisabled,
  submitLabel = "Save",
  buttonsBehavior = "coupled",
}: Props<V>): React.ReactElement => {
  const formikContext = useFormikContext<V>();
  const { values } = formikContext;
  const showSecondarySubmit = Boolean(secondarySubmit && secondarySubmitLabel);

  let secondaryButton: ReactNode;
  if (showSecondarySubmit) {
    const secondaryLabel =
      typeof secondarySubmitLabel === "function"
        ? secondarySubmitLabel(values, formikContext)
        : secondarySubmitLabel;
    const button = (
      <ActionButton
        appearance="default"
        className="formik-form-buttons__button"
        data-testid={TestIds.SecondarySubmit}
        disabled={
          buttonsBehavior === "coupled"
            ? secondarySubmitDisabled || submitDisabled
            : secondarySubmitDisabled
        }
        loading={secondarySubmitSaving}
        onClick={
          secondarySubmit
            ? () => {
                secondarySubmit(values, formikContext);
              }
            : undefined
        }
        success={secondarySubmitSaved}
        type="button"
      >
        {secondaryLabel}
      </ActionButton>
    );
    if (secondarySubmitTooltip) {
      secondaryButton = (
        <Tooltip
          message={secondarySubmitTooltip}
          position="top-center"
          positionElementClassName="u-nudge-left"
        >
          {button}
        </Tooltip>
      );
    } else {
      secondaryButton = button;
    }
  }

  return (
    <>
      <div
        className={classNames("formik-form-buttons", buttonsClassName, {
          "is-inline": inline,
        })}
        data-testid={TestIds.ButtonsWrapper}
      >
        {buttonsHelp && (
          <div
            className={classNames(
              "formik-form-buttons__help",
              buttonsHelpClassName
            )}
            data-testid={TestIds.ButtonsHelp}
          >
            {buttonsHelp}
          </div>
        )}
        {onCancel && (
          <Button
            appearance="base"
            className="formik-form-buttons__button"
            data-testid={TestIds.CancelButton}
            disabled={cancelDisabled}
            onClick={() => {
              onCancel(values, formikContext);
            }}
            type="button"
          >
            {cancelLabel}
          </Button>
        )}
        {secondaryButton}
        <ActionButton
          appearance={submitAppearance}
          className="formik-form-buttons__button"
          disabled={submitDisabled}
          loading={saving}
          success={saved}
          type="submit"
        >
          {submitLabel}
        </ActionButton>
      </div>
      {saving && savingLabel && (
        <p
          className="u-text--light u-align-text--right"
          data-testid={TestIds.SavingLabel}
        >
          {savingLabel}
        </p>
      )}
    </>
  );
};

export default FormikFormButtons;
