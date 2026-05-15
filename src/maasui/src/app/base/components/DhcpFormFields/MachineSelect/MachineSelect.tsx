import type { HTMLProps } from "react";
import { useCallback, useState } from "react";

import { useId, useOnEscapePressed } from "@canonical/react-components";
import Field from "@canonical/react-components/dist/components/Field";
import className from "classnames";
import { useFormikContext } from "formik";

import SelectButton from "../../SelectButton";

import MachineSelectBox from "./MachineSelectBox/MachineSelectBox";

import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import OutsideClickHandler from "@/app/base/components/OutsideClickHandler";
import { useFetchActions, usePreviousPersistent } from "@/app/base/hooks";
import type { FetchFilters, Machine } from "@/app/store/machine/types";
import { useFetchMachine } from "@/app/store/machine/utils/hooks";
import { tagActions } from "@/app/store/tag";

export enum Labels {
  AppliesTo = "Applies to",
  ChooseMachine = "Choose machine",
}

export type Props = {
  label?: React.ReactNode;
  defaultOption?: string;
  filters?: FetchFilters;
  displayError?: boolean;
  name: string;
  value?: HTMLProps<HTMLElement>["value"];
};

export const MachineSelect = ({
  name,
  filters,
  label = Labels.AppliesTo,
  defaultOption = Labels.ChooseMachine,
  value,
  ...props
}: Props): React.ReactElement => {
  const { setFieldValue } = useFormikContext();

  const [isOpen, setIsOpen] = useState(false);
  const labelId = useId();
  const selectId = useId();
  const handleClose = useCallback(
    () => () => {
      setIsOpen(false);
    },
    []
  );
  const handleSelect = (machine: Machine | null) => {
    handleClose();
    setFieldValue(name, machine?.system_id || null).catch((reason: unknown) => {
      throw new FormikFieldChangeError(name, "setFieldValue", reason as string);
    });
  };
  useOnEscapePressed(handleClose);
  const { machine } = useFetchMachine(value as string);
  const previousMachine = usePreviousPersistent(machine);
  const selectedMachine = machine || previousMachine;

  useFetchActions([tagActions.fetch]);

  const buttonLabel = selectedMachine?.hostname || defaultOption;

  return (
    <div className="machine-select">
      {/* TODO: update once Field allows a custom label id
      https://github.com/canonical/react-components/issues/820 */}
      <Field label={<span id={labelId}>{label}</span>} {...props}>
        <OutsideClickHandler onClick={handleClose}>
          <SelectButton
            aria-describedby={labelId}
            aria-expanded={isOpen ? "true" : "false"}
            aria-haspopup="listbox"
            aria-label={`${buttonLabel} - open list`}
            className="u-no-margin--bottom"
            id={selectId}
            onClick={() => {
              setIsOpen(!isOpen);
              if (!isOpen) {
                setFieldValue(name, "", false).catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    name,
                    "setFieldValue",
                    reason as string
                  );
                });
              }
            }}
          >
            {buttonLabel}
          </SelectButton>
          <div
            className={className("machine-select-box-wrapper", {
              "machine-select-box-wrapper--is-open": isOpen,
            })}
          >
            {isOpen ? (
              <MachineSelectBox filters={filters} onSelect={handleSelect} />
            ) : null}
          </div>
        </OutsideClickHandler>
      </Field>
    </div>
  );
};

export default MachineSelect;
