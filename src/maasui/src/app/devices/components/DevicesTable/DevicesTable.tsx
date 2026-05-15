import type { Dispatch, ReactElement, SetStateAction } from "react";
import { useEffect } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import type { RowSelectionState } from "@tanstack/react-table";
import { useDispatch, useSelector } from "react-redux";

import { useFetchActions } from "@/app/base/hooks";
import useDevicesTableColumns from "@/app/devices/components/DevicesTable/useDevicesTableColumns/useDevicesTableColumns";
import { deviceActions } from "@/app/store/device";
import deviceSelectors from "@/app/store/device/selectors";
import type { Device } from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";

import "./index.scss";

type DevicesTableProps = {
  rowSelection: RowSelectionState;
  setRowSelection: Dispatch<SetStateAction<RowSelectionState>>;
  searchFilter: string;
};

export type DeviceRow = Omit<Device, "zone"> & {
  zone: string;
};

const DevicesTable = ({
  rowSelection,
  setRowSelection,
  searchFilter,
}: DevicesTableProps): ReactElement => {
  const dispatch = useDispatch();

  useEffect(() => {
    dispatch(deviceActions.setSelected(Object.keys(rowSelection)));
  }, [dispatch, rowSelection]);

  const devices = useSelector((state: RootState) =>
    deviceSelectors.search(
      state,
      searchFilter || null,
      Object.keys(rowSelection)
    )
  );
  const devicesLoading = useSelector(deviceSelectors.loading);

  useFetchActions([deviceActions.fetch, tagActions.fetch]);

  const columns = useDevicesTableColumns();

  return (
    <GenericTable
      className="devices-table"
      columns={columns}
      data={devices.map(
        (device): DeviceRow => ({ ...device, zone: device.zone.name })
      )}
      isLoading={devicesLoading}
      noData="No devices available."
      selection={{
        rowSelection,
        setRowSelection,
        rowSelectionLabelKey: "fqdn",
      }}
      sorting={[{ id: "fqdn", desc: false }]}
    />
  );
};

export default DevicesTable;
