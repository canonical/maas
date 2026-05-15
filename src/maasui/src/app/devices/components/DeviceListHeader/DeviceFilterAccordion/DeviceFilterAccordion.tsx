import { useSelector } from "react-redux";

import FilterAccordion from "@/app/base/components/FilterAccordion";
import { useFetchActions } from "@/app/base/hooks";
import deviceSelectors from "@/app/store/device/selectors";
import { FilterDevices, getDeviceValue } from "@/app/store/device/utils";
import { tagActions } from "@/app/store/tag";
import tagSelectors from "@/app/store/tag/selectors";

type Props = {
  searchText: string;
  setSearchText: (searchText: string) => void;
};

const filterOrder = [
  "domain",
  "fabrics",
  "ip_assignment",
  "owner",
  "subnets",
  "tags",
  "zone",
];

const filterNames = new Map([
  ["domain", "Domain"],
  ["fabrics", "Fabrics"],
  ["ip_assignment", "IP assignment"],
  ["owner", "Owner"],
  ["subnets", "Subnets"],
  ["tags", "Tags"],
  ["zone", "Zone"],
]);

const DeviceFilterAccordion = ({
  searchText,
  setSearchText,
}: Props): React.ReactElement => {
  const devices = useSelector(deviceSelectors.all);
  const devicesLoaded = useSelector(deviceSelectors.loaded);
  const tags = useSelector(tagSelectors.all);

  useFetchActions([tagActions.fetch]);

  return (
    <FilterAccordion
      disabled={!devicesLoaded}
      filterNames={filterNames}
      filterOrder={filterOrder}
      filterString={searchText}
      filtersToString={FilterDevices.filtersToString}
      getCurrentFilters={FilterDevices.getCurrentFilters}
      getValue={(device, filter) => getDeviceValue(device, filter, { tags })}
      isFilterActive={FilterDevices.isFilterActive}
      items={devices}
      onUpdateFilterString={setSearchText}
      toggleFilter={FilterDevices.toggleFilter}
    />
  );
};

export default DeviceFilterAccordion;
