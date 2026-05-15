import { useRef } from "react";
import type { ReactNode } from "react";

import type { InputProps, PropsWithSpread } from "@canonical/react-components";
import { Input } from "@canonical/react-components";
import { nanoid } from "@reduxjs/toolkit";

import { someInArray } from "@/app/utils";

type Props<I> = PropsWithSpread<
  {
    handleRowCheckbox: (item: I, rows: I[]) => void;
    checkSelected?: ((item: I, rows: I[]) => boolean) | null;
    items: I[];
    // This needs to be something other than `label` to prevent conflicts with the
    // HTMLInputElement type.
    inputLabel?: ReactNode;
    item: I;
  },
  InputProps
>;

const RowCheckbox = <I,>({
  handleRowCheckbox,
  checkSelected,
  item,
  items,
  inputLabel,
  ...props
}: Props<I>): React.ReactElement => {
  const id = useRef(nanoid());
  return (
    <Input
      checked={
        checkSelected ? checkSelected(item, items) : someInArray(item, items)
      }
      className="keep-label-opacity"
      id={id.current}
      label={inputLabel}
      labelClassName="u-no-margin--bottom u-no-padding--top"
      onChange={() => {
        handleRowCheckbox(item, items);
      }}
      type="checkbox"
      wrapperClassName="u-no-margin--bottom u-nudge--checkbox"
      {...props}
    />
  );
};

export default RowCheckbox;
