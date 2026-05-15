import type { KeyboardEvent } from "react";

import { MainTable } from "@canonical/react-components";
import { highlightSubString as baseHighlightSubString } from "@canonical/react-components/dist/utils";
import { useSelector } from "react-redux";

import Placeholder from "../Placeholder";
import VisuallyHidden from "../VisuallyHidden";

import DoubleRow from "@/app/base/components/DoubleRow";
import { useFetchActions } from "@/app/base/hooks";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import { tagActions } from "@/app/store/tag";
import tagSelectors from "@/app/store/tag/selectors";
import type { Tag } from "@/app/store/tag/types";
import { getTagNamesForIds } from "@/app/store/tag/utils";

export enum Label {
  Loading = "Loading...",
  Hostname = "Hostname",
  Owner = "Owner",
}

type Props = {
  pageSize: number;
  machines: Machine[];
  onMachineClick: (machine: Machine | null) => void;
  searchText: string;
  machinesLoading?: boolean;
  setSearchText: (searchText: string) => void;
};

const safeGetRegexString = (searchText: string): string => {
  try {
    new RegExp(searchText, "i");
    return searchText;
  } catch {
    return "";
  }
};
const highlightSubString = (text: string, highlight: string) =>
  baseHighlightSubString(text, safeGetRegexString(highlight));

const generateRows = (
  machines: Machine[],
  searchText: string,
  onRowClick: (machine: Machine) => void,
  tags: Tag[]
) => {
  const highlightedText = (text: string) => (
    <span
      dangerouslySetInnerHTML={{
        __html: highlightSubString(text, searchText).text,
      }}
    />
  );
  return machines.map((machine) => ({
    "aria-label": machine.hostname,
    className: "machine-select-table__row",
    columns: [
      {
        "aria-label": Label.Hostname,
        content: (
          <DoubleRow
            primary={highlightedText(machine.hostname)}
            secondary={highlightedText(machine.system_id)}
          />
        ),
      },
      {
        "aria-label": Label.Owner,
        content: (
          <DoubleRow
            primary={machine.owner || "-"}
            secondary={
              machine.tags.length
                ? highlightedText(
                    getTagNamesForIds(machine.tags, tags).join(", ")
                  )
                : "-"
            }
          />
        ),
      },
    ],
    "data-testid": "machine-select-row",
    onClick: () => {
      onRowClick(machine);
    },
    onKeyPress: (e: KeyboardEvent<HTMLTableRowElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onRowClick(machine);
      }
    },
    tabIndex: 0,
  }));
};

const getSkeletonRows = (count = 3) =>
  Array.from(Array(count)).map((_, i) => ({
    columns: [
      {
        content: (
          <DoubleRow
            primary={<Placeholder>xxxxxxxxx.xxxx</Placeholder>}
            secondary={<Placeholder>xxxxxxxxx.xxxx</Placeholder>}
          />
        ),
      },
      {
        content: (
          <DoubleRow
            primary={<Placeholder>xxxxxxxxx.xxxx</Placeholder>}
            secondary={<Placeholder>xxxxxxxxx.xxxx</Placeholder>}
          />
        ),
      },
    ],
    "data-testid": "machine-select-row",
    tabIndex: -1,
    key: i,
  }));

export const MachineSelectTable = ({
  machines,
  machinesLoading,
  pageSize,
  onMachineClick,
  searchText,
  setSearchText,
}: Props): React.ReactElement => {
  const tags = useSelector(tagSelectors.all);
  const loadingMachines = useSelector(machineSelectors.loading);

  useFetchActions([tagActions.fetch]);

  const rows = generateRows(
    machines,
    searchText,
    (machine) => {
      setSearchText(machine.hostname);
      onMachineClick(machine);
    },
    tags
  );

  const skeletonRows = getSkeletonRows(pageSize);

  return (
    <>
      <MainTable
        aria-busy={machinesLoading || loadingMachines ? "true" : "false"}
        emptyStateMsg={
          !machinesLoading ? "No machines match the search criteria." : null
        }
        headers={[
          {
            content: (
              <>
                <div>{Label.Hostname}</div>
                <div>system_id</div>
              </>
            ),
          },
          {
            content: (
              <>
                <div>{Label.Owner}</div>
                <div>Tags</div>
              </>
            ),
          },
        ]}
        rows={machinesLoading ? skeletonRows : rows}
      />
      <VisuallyHidden>
        <div aria-live="polite">{machinesLoading ? "loading" : null}</div>
      </VisuallyHidden>
    </>
  );
};

export default MachineSelectTable;
