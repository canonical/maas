import FabricsTable from "./components/FabricsTable";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import NetworksHeader from "@/app/networks/components/NetworksHeader";

const FabricsList = () => {
  useWindowTitle("Fabrics");

  return (
    <PageContent header={<NetworksHeader />}>
      <FabricsTable />
    </PageContent>
  );
};

export default FabricsList;
