import type { ReactElement } from "react";

import pluralize from "pluralize";

import DoubleRow from "@/app/base/components/DoubleRow";

export enum Label {
  HideGroup = "Hide",
  ShowGroup = "Show",
}

type GroupRowProps = {
  itemName: string;
  groupName: string;
  count: number;
};

const GroupRow = ({
  itemName,
  groupName,
  count,
}: GroupRowProps): ReactElement => {
  return (
    <>
      <DoubleRow
        primary={<strong>{groupName}</strong>}
        secondary={<span>{pluralize(itemName, count, true)}</span>}
      />
    </>
  );
};

export default GroupRow;
