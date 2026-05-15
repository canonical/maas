import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";

import APIKeyForm from "../APIKeyForm";

import { useFetchActions } from "@/app/base/hooks";
import type { RootState } from "@/app/store/root/types";
import { tokenActions } from "@/app/store/token";
import tokenSelectors from "@/app/store/token/selectors";
import type { Token } from "@/app/store/token/types";

export enum Label {
  NotFound = "API key not found",
}

export const APIKeyEdit = ({ id }: { id: Token["id"] }): React.ReactElement => {
  useFetchActions([tokenActions.fetch]);

  const loading = useSelector(tokenSelectors.loading);
  const token = useSelector((state: RootState) =>
    tokenSelectors.getById(state, id)
  );
  if (loading) {
    return <Spinner text="Loading..." />;
  }
  if (!token) {
    return <h4>{Label.NotFound}</h4>;
  }
  return <APIKeyForm token={token} />;
};

export default APIKeyEdit;
