import { GenericTable } from "@canonical/maas-react-components";
import { Notification as NotificationBanner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import type { TokenRowData } from "./useAPIKeyTableColumns/useAPIKeyTableColumns";
import useAPIKeyTableColumns from "./useAPIKeyTableColumns/useAPIKeyTableColumns";

import { useFetchActions } from "@/app/base/hooks";
import { tokenActions } from "@/app/store/token";
import tokenSelectors from "@/app/store/token/selectors";
import type { Token } from "@/app/store/token/types";

export enum Label {
  Title = "API keys",
  EmptyList = "No API keys available.",
}

const generateRows = (tokens: Token[]): TokenRowData[] => {
  return tokens.map((token) => ({
    id: token.id,
    name: token.consumer.name,
    key: `${token.consumer.key}:${token.key}:${token.secret}`,
  }));
};

const APIKeyList = (): React.ReactElement => {
  const errors = useSelector(tokenSelectors.errors);
  const loading = useSelector(tokenSelectors.loading);
  const tokens = useSelector(tokenSelectors.all);

  useFetchActions([tokenActions.fetch]);
  const columns = useAPIKeyTableColumns();

  return (
    <>
      {errors && typeof errors === "string" && (
        <NotificationBanner severity="negative" title="Error:">
          {errors}
        </NotificationBanner>
      )}
      <GenericTable
        aria-label={Label.Title}
        className="apikey-list"
        columns={columns}
        data={generateRows(tokens)}
        isLoading={loading}
        noData={Label.EmptyList}
      />
    </>
  );
};

export default APIKeyList;
