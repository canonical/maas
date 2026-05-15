import { useEffect } from "react";

import { useDispatch, useSelector } from "react-redux";
import type { AnyAction } from "redux";

import statusSelectors from "@/app/store/status/selectors";

/**
 * A hook to run a set of actions once on mount and again when the websocket
 * reconnects.
 * @param {Array<() => AnyAction>} actions - The actions to run.
 */
export const useFetchActions = (actions: (() => AnyAction)[]): void => {
  const dispatch = useDispatch();
  const connectedCount = useSelector(statusSelectors.connectedCount);

  useEffect(() => {
    actions.forEach((action) => {
      dispatch(action());
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch, connectedCount]);
};
