import { RepositoriesTable } from "../components";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";

export const RepositoriesList = (): React.ReactElement => {
  useWindowTitle("Package repos");

  return (
    <PageContent>
      <RepositoriesTable />
    </PageContent>
  );
};

export default RepositoriesList;
