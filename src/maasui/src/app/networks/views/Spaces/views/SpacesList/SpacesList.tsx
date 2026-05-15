import SpacesTable from "./components/SpacesTable";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import NetworksHeader from "@/app/networks/components/NetworksHeader";

const SpacesList = () => {
  useWindowTitle("Spaces");

  return (
    <PageContent header={<NetworksHeader />}>
      <SpacesTable />
    </PageContent>
  );
};

export default SpacesList;
