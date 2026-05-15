import type { ReactElement } from "react";

import { GenericTable, MainToolbar } from "@canonical/maas-react-components";
import {
  Button,
  Notification as NotificationBanner,
} from "@canonical/react-components";

import { useGetSslKeys } from "@/app/api/query/sslKeys";
import { useSidePanel } from "@/app/base/side-panel-context";
import { AddSSLKey } from "@/app/preferences/views/SSLKeys/components";
import useSSLKeysTableColumns from "@/app/preferences/views/SSLKeys/components/SSLKeysTable/useSSLKeysTableColumns/useSSLKeysTableColumns";

const SSLKeysTable = (): ReactElement => {
  const { openSidePanel } = useSidePanel();
  const { data, failureReason, isPending } = useGetSslKeys();
  const sslKeys = data?.items ?? [];

  const columns = useSSLKeysTableColumns();

  return (
    <div className="ssl-keys-table" data-testid="ssl-keys-table">
      {failureReason && (
        <NotificationBanner severity="negative" title="Error:">
          {failureReason.message}
        </NotificationBanner>
      )}
      <MainToolbar>
        <MainToolbar.Controls>
          <Button
            onClick={() => {
              openSidePanel({ component: AddSSLKey, title: "Add SSL key" });
            }}
          >
            Add SSL key
          </Button>
        </MainToolbar.Controls>
      </MainToolbar>
      <GenericTable
        aria-label="SSL keys"
        columns={columns}
        data={sslKeys}
        isLoading={isPending}
        noData="No SSL keys available."
        variant="regular"
      />
    </div>
  );
};

export default SSLKeysTable;
