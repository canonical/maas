import { useRef } from "react";
import type { ReactNode } from "react";

import type { InputProps, PropsWithSpread } from "@canonical/react-components";
import { Input } from "@canonical/react-components";
import { nanoid } from "@reduxjs/toolkit";
import classNames from "classnames";

import type { CheckboxHandlers } from "@/app/utils/generateCheckboxHandlers";

type Props<S> = PropsWithSpread<
  {
    checkAllSelected?: CheckboxHandlers<S>["checkAllSelected"] | null;
    checkSelected?: CheckboxHandlers<S>["checkSelected"] | null;
    disabled?: boolean;
    handleGroupCheckbox: CheckboxHandlers<S>["handleGroupCheckbox"];
    inRow?: boolean;
    items: S[];
    // This needs to be something other than `label` to prevent conflicts with the
    // HTMLInputElement type.
    inputLabel?: ReactNode;
    selectedItems: S[];
  },
  InputProps
>;

const GroupCheckbox = <S,>({
  checkAllSelected,
  checkSelected,
  disabled,
  handleGroupCheckbox,
  inRow,
  items,
  inputLabel,
  selectedItems,
  ...props
}: Props<S>): React.ReactElement => {
  const id = useRef(nanoid());
  const allSelected = checkAllSelected
    ? checkAllSelected(items, selectedItems)
    : selectedItems.length > 0 && selectedItems.length === items.length;
  const someSelected =
    !allSelected && checkSelected
      ? checkSelected(items, selectedItems)
      : selectedItems.length > 0 && !allSelected;

  return (
    <Input
      aria-checked={allSelected ? "true" : someSelected ? "mixed" : "false"}
      checked={someSelected || allSelected}
      disabled={items.length === 0 || disabled}
      id={id.current}
      label={inputLabel ? inputLabel : " "}
      labelClassName="u-no-margin--bottom u-no-padding--top"
      onChange={() => {
        handleGroupCheckbox(items, selectedItems);
      }}
      type="checkbox"
      wrapperClassName={classNames("u-no-margin--bottom u-nudge--checkbox", {
        "u-align-header-checkbox": !inRow,
      })}
      {...props}
    />
  );
};

export default GroupCheckbox;
