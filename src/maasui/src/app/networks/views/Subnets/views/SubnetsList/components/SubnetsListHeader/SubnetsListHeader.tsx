import type { ChangeEvent, ReactElement } from "react";
import { useCallback, useEffect } from "react";

import { Select } from "@canonical/react-components";
import { useNavigate } from "react-router";

import { SubnetsUrlParams } from "../../SubnetsList";
import { SubnetsColumns } from "../SubnetsTable/constants";
import type { GroupByKey } from "../SubnetsTable/types";

import DebounceSearchBox from "@/app/base/components/DebounceSearchBox";
import type { SyncNavigateFunction } from "@/app/base/types";
import NetworksHeader from "@/app/networks/components/NetworksHeader";

const subnetGroupingOptions = [
  {
    label: "Group by fabric",
    value: SubnetsColumns.FABRIC,
  },
  {
    label: "Group by space",
    value: SubnetsColumns.SPACE,
  },
];

type SubnetsListHeaderProps = {
  searchText: string;
  setSearchText: (text: string) => void;
  grouping: string | null;
};

const SubnetsListHeader = ({
  searchText,
  setSearchText,
  grouping,
}: SubnetsListHeaderProps): ReactElement => {
  const navigate: SyncNavigateFunction = useNavigate();

  const setGrouping = useCallback(
    (group: GroupByKey | null) => {
      const search = `?${SubnetsUrlParams.By}=${group}&${SubnetsUrlParams.Q}=${searchText}`;
      if (location.search !== search) {
        navigate(
          {
            pathname: "/networks/subnets",
            search,
          },
          { replace: true }
        );
      }
    },
    [navigate, searchText]
  );

  const handleSearch = useCallback(
    (searchText: string) => {
      const search = `?${SubnetsUrlParams.By}=${grouping}&${SubnetsUrlParams.Q}=${searchText}`;
      if (location.search !== search) {
        navigate(
          {
            pathname: "/networks/subnets",
            search: `?${SubnetsUrlParams.By}=${grouping}&${SubnetsUrlParams.Q}=${searchText}`,
          },
          { replace: true }
        );
      }
    },
    [navigate, grouping]
  );

  const hasValidGroupBy = grouping && ["fabric", "space"].includes(grouping);

  useEffect(() => {
    if (!hasValidGroupBy) {
      setGrouping("fabric");
    }
  }, [grouping, setGrouping, hasValidGroupBy]);

  return (
    <NetworksHeader
      controls={
        <>
          <DebounceSearchBox
            onDebounced={handleSearch}
            searchText={searchText}
            setSearchText={setSearchText}
          />
          <Select
            aria-label="Group by"
            className="u-no-padding--right subnet-group__select"
            defaultValue={grouping || ""}
            name="network-groupings"
            onChange={(e: ChangeEvent<HTMLSelectElement>) => {
              setGrouping((e.target.value as GroupByKey) ?? null);
            }}
            options={subnetGroupingOptions}
          />
        </>
      }
    />
  );
};

export default SubnetsListHeader;
