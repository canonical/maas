import { Outlet } from "react-router";

import { useGetIsSuperUser } from "@/app/api/query/auth";
import PageContent from "@/app/base/components/PageContent";
import SectionHeader from "@/app/base/components/SectionHeader";
import { useFetchActions } from "@/app/base/hooks";
import { configActions } from "@/app/store/config";

const Settings = (): React.ReactElement => {
  const isSuperUser = useGetIsSuperUser();

  useFetchActions([configActions.fetch]);

  if (!isSuperUser.data) {
    return (
      <PageContent
        header={
          <SectionHeader title="You do not have permission to view this page." />
        }
      />
    );
  }

  return <Outlet />;
};

export default Settings;
