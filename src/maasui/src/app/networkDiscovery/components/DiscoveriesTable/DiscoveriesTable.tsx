import type { ReactElement } from "react";
import { useState } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { Col, Row } from "@canonical/react-components";

import { useNetworkDiscoveries } from "@/app/api/query/networkDiscovery";
import SearchBox from "@/app/base/components/SearchBox";
import DiscoveriesFilterAccordion from "@/app/networkDiscovery/components/DiscoveriesTable/DiscoveriesFilterAccordion";
import useDiscoveriesTableColumns from "@/app/networkDiscovery/components/DiscoveriesTable/useDiscoveriesTableColumns/useDiscoveriesTableColumns";
import { Labels } from "@/app/networkDiscovery/views/DiscoveriesList/DiscoveriesList";
import { FilterDiscoveries } from "@/app/store/discovery/utils";

const DiscoveriesTable = (): ReactElement => {
  const [searchString, setSearchString] = useState("");
  const { data, isLoading } = useNetworkDiscoveries();
  const allDiscoveries = data?.items ?? [];

  const discoveries = FilterDiscoveries.filterItems(
    allDiscoveries,
    searchString ?? ""
  );

  const loading = isLoading;

  const columns = useDiscoveriesTableColumns();

  return (
    <div aria-label={Labels.DiscoveriesList}>
      <Row>
        <Col size={3}>
          <DiscoveriesFilterAccordion
            searchText={searchString}
            setSearchText={setSearchString}
          />
        </Col>
        <Col size={9}>
          <SearchBox
            data-testid="discoveries-search"
            externallyControlled
            onChange={setSearchString}
            value={searchString}
          />
        </Col>
      </Row>
      <GenericTable
        className="p-table--network-discoveries p-table-expanding--light"
        columns={columns}
        data={discoveries}
        data-testid="discoveries-table"
        isLoading={loading}
        noData={
          !!searchString
            ? "No discoveries match the search criteria."
            : "No discoveries available."
        }
        sorting={[{ id: "last_seen", desc: false }]}
      />
    </div>
  );
};

export default DiscoveriesTable;
