import type { Dispatch, SetStateAction } from "react";
import { useEffect } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import type { RowSelectionState } from "@tanstack/react-table";
import { useDispatch, useSelector } from "react-redux";

import useControllersTableColumns from "./useControllersTableColumns/useControllersTableColumns";

import { controllerActions } from "@/app/store/controller";
import controllerSelectors from "@/app/store/controller/selectors";
import type { Controller } from "@/app/store/controller/types";
import { vaultEnabled as vaultEnabledSelectors } from "@/app/store/general/selectors";
import type { RootState } from "@/app/store/root/types";

type ControllersTableProps = {
  rowSelection: RowSelectionState;
  setRowSelection: Dispatch<SetStateAction<RowSelectionState>>;
  isPending: boolean;
  controllers: Controller[];
};

const ControllersTable = ({
  rowSelection,
  setRowSelection,
  isPending,
  controllers,
}: ControllersTableProps) => {
  const dispatch = useDispatch();

  useEffect(() => {
    dispatch(controllerActions.setSelected(Object.keys(rowSelection)));
  }, [dispatch, rowSelection]);

  const { configuredControllers } = useSelector((state: RootState) =>
    controllerSelectors.getVaultConfiguredControllers(state)
  );

  const vaultEnabled = useSelector(vaultEnabledSelectors.get);

  const columns = useControllersTableColumns({
    vaultEnabled,
    configuredControllers: configuredControllers.length,
  });

  return (
    <GenericTable
      aria-label="controllers list"
      className="controllers-table"
      columns={columns}
      data={controllers}
      isLoading={isPending}
      noData="No controllers available."
      selection={{
        rowSelection,
        setRowSelection,
        rowSelectionLabelKey: "fqdn",
      }}
      sorting={[{ id: "fqdn", desc: false }]}
      variant="regular"
    />
  );
};

export default ControllersTable;
