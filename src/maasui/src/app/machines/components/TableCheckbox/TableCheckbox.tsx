import type { ReactNode } from "react";

import type { InputProps, PropsWithSpread } from "@canonical/react-components";
import { Input } from "@canonical/react-components";
import classNames from "classnames";
import { useSelector, useDispatch } from "react-redux";

import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { SelectedMachines } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";

export enum Checked {
  Checked = "true",
  Mixed = "mixed",
  Unchecked = "false",
}

type Props = PropsWithSpread<
  {
    callId?: string | null;
    extraClasses?: string;
    inputLabel?: ReactNode;
    isChecked: Checked;
    isDisabled?: boolean;
    onGenerateSelected: (
      checked: boolean,
      isRange: boolean
    ) => SelectedMachines | null;
  },
  InputProps
>;

const TableCheckbox = ({
  callId,
  extraClasses,
  inputLabel,
  isChecked,
  isDisabled,
  onGenerateSelected,
  ...props
}: Props): React.ReactElement => {
  const dispatch = useDispatch();
  const machineCount = useSelector((state: RootState) =>
    machineSelectors.listCount(state, callId)
  );

  return (
    <Input
      aria-checked={isChecked}
      checked={isChecked !== Checked.Unchecked}
      disabled={machineCount === 0 || isDisabled}
      label={inputLabel}
      labelClassName="u-no-margin--bottom u-no-padding--top"
      onChange={(
        event: React.ChangeEvent<HTMLInputElement> & {
          nativeEvent: React.PointerEvent;
        }
      ) => {
        // prevent default text range selection when 'shift' key is pressed
        window.getSelection()?.removeAllRanges();
        const isRange = event.nativeEvent.shiftKey;
        dispatch(
          machineActions.setSelected(
            onGenerateSelected(event.target.checked, isRange)
          )
        );
      }}
      type="checkbox"
      wrapperClassName={classNames(
        "u-no-margin--bottom u-nudge--checkbox p-checkbox--non-disabled-label",
        extraClasses
      )}
      {...props}
    />
  );
};

export default TableCheckbox;
