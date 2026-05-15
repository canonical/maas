import type { ReactElement } from "react";
import { useState } from "react";

import { SubnetsListHeader, SubnetsTable } from "./components";
import type { GroupByKey } from "./components/SubnetsTable/types";

import PageContent from "@/app/base/components/PageContent/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { useQuery } from "@/app/base/hooks/urls";

export const SubnetsUrlParams = {
  By: "by",
  Q: "q",
};

const SubnetsList = (): ReactElement => {
  useWindowTitle("Subnets");
  const query = useQuery();
  const [searchText, setSearchText] = useState<string>(
    query.get(SubnetsUrlParams.Q) || ""
  );
  const grouping = query.get(SubnetsUrlParams.By);

  const hasValidGroupBy = grouping && ["fabric", "space"].includes(grouping);

  return (
    <PageContent
      header={
        <SubnetsListHeader
          grouping={grouping}
          searchText={searchText}
          setSearchText={setSearchText}
        />
      }
    >
      {hasValidGroupBy ? (
        <SubnetsTable
          groupBy={grouping as GroupByKey}
          searchText={searchText}
        />
      ) : null}
    </PageContent>
  );
};

export default SubnetsList;
