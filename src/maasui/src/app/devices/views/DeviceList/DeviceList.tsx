import type { ReactElement } from "react";
import { useCallback, useState } from "react";

import type { RowSelectionState } from "@tanstack/react-table";
import { useLocation, useNavigate } from "react-router";

import PageContent from "@/app/base/components/PageContent";
import { DeviceListHeader, DevicesTable } from "@/app/devices/components";
import { FilterDevices } from "@/app/store/device/utils";

const DeviceList = (): ReactElement => {
  const navigate = useNavigate();
  const location = useLocation();

  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  const [searchFilter, _setSearchFilter] = useState(
    FilterDevices.filtersToString(
      FilterDevices.queryStringToFilters(location.search)
    )
  );

  const setSearchFilter = useCallback(
    async (searchText: string) => {
      _setSearchFilter(searchText);
      await navigate({
        search: FilterDevices.filtersToQueryString(
          FilterDevices.getCurrentFilters(searchText)
        ),
      });
    },
    [navigate, _setSearchFilter]
  );

  return (
    <PageContent
      header={
        <DeviceListHeader
          rowSelection={rowSelection}
          searchFilter={searchFilter}
          setRowSelection={setRowSelection}
          setSearchFilter={setSearchFilter}
        />
      }
    >
      <DevicesTable
        rowSelection={rowSelection}
        searchFilter={searchFilter}
        setRowSelection={setRowSelection}
      />
    </PageContent>
  );
};

export default DeviceList;
