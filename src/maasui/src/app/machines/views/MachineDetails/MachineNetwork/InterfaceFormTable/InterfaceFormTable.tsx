import { useEffect, useMemo, useState } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import type { RowSelectionState } from "@tanstack/react-table";
import { useSelector } from "react-redux";

import useInterfaceFormTableColumns from "./useInterfaceFormTableColumns/useInterfaceFormTableColumns";

import type {
  Selected,
  SetSelected,
} from "@/app/base/components/node/networking/types";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine, MachineDetails } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";
import {
  getInterfaceById,
  getInterfaceName,
  getLinkFromNic,
} from "@/app/store/utils";
import { simpleSortByKey } from "@/app/utils";

import "./_index.scss";

export type InterfaceRow = {
  linkId?: NetworkLink["id"] | null;
  nicId?: NetworkInterface["id"] | null;
};

export type InterfaceTableRow = {
  id: number;
  name: string;
  nic: NetworkInterface | null;
  link: NetworkLink | null;
  machine: MachineDetails;
  nicId: NetworkInterface["id"] | null | undefined;
  linkId: NetworkLink["id"] | null | undefined;
};

const selectedToRowSelection = (
  selectedItems: Selected[],
  rows: InterfaceTableRow[]
): RowSelectionState =>
  rows.reduce<RowSelectionState>((acc, row) => {
    const isSelected = selectedItems.some((s) => s.nicId === row.id);
    if (isSelected) acc[row.id] = true;
    return acc;
  }, {});

type Props = {
  interfaces: InterfaceRow[];
  selected?: Selected[];
  selectedEditable?: boolean;
  setSelected?: SetSelected | null;
  systemId: Machine["system_id"];
};

const InterfaceFormTable = ({
  interfaces,
  selected = [],
  selectedEditable,
  setSelected,
  systemId,
}: Props): React.ReactElement => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const columns = useInterfaceFormTableColumns();

  const isLoading = !isMachineDetails(machine);

  const rows = useMemo<InterfaceTableRow[]>(
    () =>
      isLoading
        ? []
        : interfaces
            .map(({ nicId, linkId }) => {
              const nic = getInterfaceById(
                machine as MachineDetails,
                nicId,
                linkId
              );
              const link = getLinkFromNic(nic, linkId);
              const id = getInterfaceName(machine as MachineDetails, nic, link);
              return {
                id: nic!.id,
                name: id,
                nic,
                link,
                machine: machine as MachineDetails,
                nicId,
                linkId,
              };
            })
            .sort(simpleSortByKey("id")),
    [interfaces, isLoading, machine]
  );

  const [rowSelection, setRowSelection] = useState<RowSelectionState>(() =>
    selectedToRowSelection(selected, rows)
  );

  useEffect(() => {
    if (!setSelected) return;
    const selectedKeys = Object.keys(
      selectedToRowSelection(selected, rows)
    ).sort();
    const rowSelectionKeys = Object.keys(rowSelection)
      .filter((key) => rowSelection[key])
      .sort();
    if (selectedKeys.join(",") !== rowSelectionKeys.join(",")) {
      const newSelected = rows
        .filter((row) => rowSelection[row.id])
        .map((row) => ({ nicId: row.nicId, linkId: row.linkId }));
      setSelected(newSelected);
    }
  }, [rowSelection, selected, setSelected, rows]);

  return (
    <>
      <GenericTable
        className="interface-form-table"
        columns={columns}
        data={rows}
        isLoading={isLoading}
        noData="No interfaces available."
        selection={
          selectedEditable && setSelected
            ? {
                rowSelection,
                setRowSelection,
                rowSelectionLabelKey: "name",
              }
            : undefined
        }
        variant="regular"
      />
    </>
  );
};

export default InterfaceFormTable;
