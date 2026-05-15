import type { AnyAction } from "redux";
import { select, type SagaGenerator, put } from "typed-redux-saga";

import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import { MachineMeta } from "@/app/store/machine/types";
import type { WebSocketAction } from "@/websocket-client";

/**
 * Handle unsubscribing from unused entities and cleaning up the request.
 * @param action - A websocket action.
 */
export function* handleUnsubscribe(
  action: WebSocketAction
): SagaGenerator<void> {
  const callId = action.meta.callId;
  if (callId) {
    // Unsubscribing is only supported for machines.
    if (action.meta.model === MachineMeta.MODEL) {
      const unusedIds = yield* select(
        machineSelectors.unusedIdsInCall,
        action.meta.callId
      );
      if (unusedIds.length > 0) {
        yield* put(machineActions.unsubscribe(unusedIds));
      }
      // Remove the machines after unsubscribing so that the request is still in
      // Redux when the selector above runs.
      // The request should always be removed, as the unsubscribe happens when
      // the last request that references the machine is removed.
      yield* put(machineActions.removeRequest(callId));
    }
  }
}

/**
 * Whether this is an action that stops polling a websocket request.
 * @param {Object} action.
 * @returns {Bool} - action is a request action.
 */
export const isUnsubscribeAction = (action: AnyAction): boolean =>
  Boolean(action?.meta?.unsubscribe);
