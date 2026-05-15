import type { ReactElement } from "react";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { PoolsListHeader, PoolsTable } from "@/app/pools/components";

const PoolsList = (): ReactElement => {
  useWindowTitle("Pools");

  return (
    <PageContent header={<PoolsListHeader />}>
      <PoolsTable />
    </PageContent>
  );
};

export default PoolsList;
