import GroupsTable from "./components/GroupsTable";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";

const GroupsList = () => {
  useWindowTitle("Groups");
  return (
    <PageContent>
      <GroupsTable />
    </PageContent>
  );
};
export default GroupsList;
