import type { CallEffect } from "redux-saga/effects";
import { call, put, type SagaGenerator } from "typed-redux-saga";

import type { NextActionCreator } from "../../actions";

import type {
  WebSocketRequest,
  WebSocketResponseResult,
} from "@/websocket-client";

// A map of request ids to action creators. This is used to dispatch actions
// when a response is received.
export const nextActions = new Map<
  WebSocketRequest["request_id"],
  NextActionCreator[]
>();

/**
 * Store the actions to dispatch when the response is received.
 *
 * @param {Object} action - A Redux action.
 * @param {Array} requestIDs - A list of ids for the requests associated with
 * this action.
 */
export function* storeNextActions(
  requestIDs: WebSocketRequest["request_id"][],
  nextActionCreators?: NextActionCreator[]
): Generator<
  SagaGenerator<
    Map<number, NextActionCreator[]>,
    CallEffect<Map<number, NextActionCreator[]>>
  >,
  void,
  unknown
> {
  if (nextActionCreators) {
    for (const id of requestIDs) {
      yield call([nextActions, nextActions.set], id, nextActionCreators);
    }
  }
}

/**
 * Handle dispatching the next actions, if required.
 *
 * @param {Object} response - A websocket response.
 */
export function* handleNextActions({
  request_id,
  result,
}: WebSocketResponseResult): SagaGenerator<void> {
  const actionCreators = yield* call(
    [nextActions, nextActions.get],
    request_id
  );
  if (actionCreators && actionCreators.length) {
    for (const actionCreator of actionCreators) {
      // Generate the action object using the result from the response.
      const action = yield* call(actionCreator, result);
      // Dispatch the action.
      yield* put(action);
    }
    // Clean up the stored action creators.
    yield* call([nextActions, nextActions.delete], request_id);
  }
}
