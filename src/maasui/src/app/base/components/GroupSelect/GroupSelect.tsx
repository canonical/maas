import { Select } from "@canonical/react-components";
import classNames from "classnames";

type Props<T> = {
  className?: string;
  grouping: T | null;
  groupOptions: { value: T | string; label: string }[];
  name?: string;
  setGrouping: (group: T | null) => void;
  setHiddenGroups?: (groups: string[]) => void;
};

const GroupSelect = <T extends string>({
  grouping,
  setGrouping,
  setHiddenGroups,
  groupOptions,
  name,
  className,
}: Props<T>): React.ReactElement => {
  return (
    <Select
      aria-label="Group by"
      className={classNames("u-no-padding--right", className)}
      defaultValue={grouping ?? ""}
      name={name || "machine-groupings"}
      onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
        setGrouping((e.target.value as T) ?? null);
        setHiddenGroups && setHiddenGroups([]);
      }}
      options={groupOptions}
    />
  );
};

export default GroupSelect;
