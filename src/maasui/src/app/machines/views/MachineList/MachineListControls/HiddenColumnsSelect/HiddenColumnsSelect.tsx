import {
  CheckboxInput,
  ContextualMenu,
  Icon,
} from "@canonical/react-components";

import type { MachineListControlsProps } from "../MachineListControls";

import { useSendAnalytics } from "@/app/base/hooks";
import { columnLabels, columnToggles } from "@/app/machines/constants";

type Props = Pick<MachineListControlsProps, "setHiddenColumns"> & {
  hiddenColumns: string[];
};

const HiddenColumnsSelect = ({
  hiddenColumns,
  setHiddenColumns,
}: Props): React.ReactElement => {
  const sendAnalytics = useSendAnalytics();
  const selectedColumnsLength = columnToggles.length - hiddenColumns.length;
  const someColumnsChecked =
    selectedColumnsLength > 0 && selectedColumnsLength < columnToggles.length;
  const toggleHiddenColumn = (column: string): void => {
    if (hiddenColumns.includes(column)) {
      setHiddenColumns(hiddenColumns.filter((c) => c !== column));
    } else {
      setHiddenColumns([...hiddenColumns, column]);
    }
  };
  return (
    <ContextualMenu
      className="is-maas-select"
      constrainPanelWidth
      dropdownProps={{ "aria-label": "columns menu" }}
      position="left"
      toggleClassName="hidden-columns-toggle has-icon"
      toggleLabel={
        <>
          <Icon name="settings" /> Columns
        </>
      }
      toggleLabelFirst={true}
    >
      <div className="hidden-columns-select-wrapper u-no-padding--bottom">
        <CheckboxInput
          checked={hiddenColumns.length === 0}
          indeterminate={someColumnsChecked}
          label={`${selectedColumnsLength} out of ${columnToggles.length} selected`}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            const isChecked = e.target.checked;
            sendAnalytics(
              "MachineListControls",
              isChecked ? "select" : "deselect",
              "all"
            );
            if (isChecked) {
              setHiddenColumns([]);
            } else {
              setHiddenColumns(columnToggles);
            }
          }}
        />
      </div>
      <hr />
      <div className="hidden-columns-select-wrapper u-no-padding--top">
        {columnToggles.map((column) => (
          <CheckboxInput
            aria-label={column}
            checked={!hiddenColumns.includes(column)}
            key={column}
            label={columnLabels[column]}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
              const isChecked = e.target.checked;
              sendAnalytics(
                "MachineListControls",
                isChecked ? "select" : "deselect",
                columnLabels[column]
              );
              toggleHiddenColumn(column);
            }}
          />
        ))}
      </div>
    </ContextualMenu>
  );
};

export default HiddenColumnsSelect;
