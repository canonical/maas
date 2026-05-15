import { useNetworkDiscoveries } from "@/app/api/query/networkDiscovery";
import FilterAccordion from "@/app/base/components/FilterAccordion";
import {
  FilterDiscoveries,
  getDiscoveryValue,
} from "@/app/store/discovery/utils";

type Props = {
  searchText?: string;
  setSearchText: (searchText: string) => void;
};

export enum Labels {
  FilterDiscoveries = "Filter discoveries",
}

const filterOrder = ["fabric_name", "vlan", "observer_hostname", "subnet"];

const filterNames = new Map([
  ["fabric_name", "Fabric"],
  ["observer_hostname", "Rack"],
  ["subnet", "Subnet"],
  ["vlan", "VLAN"],
]);

const DiscoveriesFilterAccordion = ({
  searchText,
  setSearchText,
}: Props): React.ReactElement => {
  const discoveries = useNetworkDiscoveries();

  const effectiveSearchText = searchText ?? "";

  const filteredDiscoveries = FilterDiscoveries.filterItems(
    discoveries.data?.items ?? [],
    effectiveSearchText
  );

  return (
    <FilterAccordion
      aria-label={Labels.FilterDiscoveries}
      disabled={!discoveries.isSuccess}
      filterNames={filterNames}
      filterOrder={filterOrder}
      filterString={effectiveSearchText}
      filtersToString={FilterDiscoveries.filtersToString}
      getCurrentFilters={FilterDiscoveries.getCurrentFilters}
      getValue={getDiscoveryValue}
      isFilterActive={FilterDiscoveries.isFilterActive}
      items={filteredDiscoveries}
      onUpdateFilterString={setSearchText}
      toggleFilter={FilterDiscoveries.toggleFilter}
    />
  );
};

export default DiscoveriesFilterAccordion;
