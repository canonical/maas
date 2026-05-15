import type { ReactElement } from "react";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { ZonesListHeader, ZonesTable } from "@/app/zones/components";

const ZonesList = (): ReactElement => {
  useWindowTitle("Zones");

  return (
    <PageContent header={<ZonesListHeader />}>
      <ZonesTable />
    </PageContent>
  );
};

export default ZonesList;
