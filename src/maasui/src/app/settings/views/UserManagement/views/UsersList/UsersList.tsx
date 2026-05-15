import type { ReactElement } from "react";

import { Notification as NotificationBanner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { UsersTable } from "@/app/settings/views/UserManagement/views/UsersList/components";
import statusSelectors from "@/app/store/status/selectors";

const UsersList = (): ReactElement => {
  const externalAuthURL = useSelector(statusSelectors.externalAuthURL);

  useWindowTitle("Users");

  if (externalAuthURL) {
    return (
      <NotificationBanner severity="information">
        Users for this MAAS are managed using an external service
      </NotificationBanner>
    );
  }

  return (
    <PageContent>
      <UsersTable />
    </PageContent>
  );
};

export default UsersList;
