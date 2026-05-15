import type { AnyAction } from "redux";
import { cancel, cancelled, delay, fork, put, take } from "typed-redux-saga";
import type { SagaGenerator } from "typed-redux-saga/macro";

import type { WebSocketAction } from "@/websocket-client";

const DEFAULT_POLL_INTERVAL = 10000;

type PollRequestId = string;

// A store of websocket endpoints that are being polled.
export const pollingRequests = new Set<PollRequestId>();

export const pollRequestId = (
  action: AnyAction | WebSocketAction
): PollRequestId => {
  const endpoint = `${action.meta?.model}.${action.meta?.method}`;
  const id = action.meta?.pollId;
  return id ? `${endpoint}:${id}` : endpoint;
};

/**
 * Whether this action is already being polled.
 * @param {Object} action.
 * @returns {Bool} - action is a request action.
 */
export const isPolling = (action: AnyAction): boolean =>
  pollingRequests.has(pollRequestId(action));

/**
 * Whether this is an action that starts polling a websocket request.
 * @param {Object} action.
 * @returns {Bool} - action is a request action.
 */
export const isStartPollingAction = (
  action: AnyAction | null | undefined
): boolean => {
  if (!action || !action.meta) {
    return false;
  }
  return (
    Boolean(action.meta.poll) &&
    // Ignore actions that are already being polled.
    !isPolling(action)
  );
};

/**
 * Whether this is an action that stops polling a websocket request.
 * @param {Object} action.
 * @returns {Bool} - action is a request action.
 */
export const isStopPollingAction = (action: AnyAction): boolean =>
  Boolean(action?.meta?.pollStop);

/**
 * Run a timer to keep dispatching an action.
 * @param action - A websocket action.
 */
export function* pollAction(action: WebSocketAction): SagaGenerator<void> {
  const id = pollRequestId(action);
  try {
    while (true) {
      // The delay is put first as the action will have already been handled
      // when it is first dispatched, so this should start by waiting until the
      // next interval.
      yield* delay(action.meta?.pollInterval || DEFAULT_POLL_INTERVAL);
      yield* put(action);
    }
  } finally {
    if (yield* cancelled()) {
      yield* put({
        type: `${action.type}PollingStopped`,
        meta: { pollId: action.meta?.pollId },
      });
      pollingRequests.delete(id);
    }
  }
}

/**
 * Handle starting and stopping a polling action.
 * @param action - A websocket action.
 */
export function* handlePolling(action: WebSocketAction): SagaGenerator<void> {
  const id = pollRequestId(action);
  pollingRequests.add(id);
  let poll = true;
  while (poll) {
    yield* put({
      type: `${action.type}PollingStarted`,
      meta: { pollId: action.meta?.pollId },
    });
    // Start polling the action.
    const pollingTask = yield* fork(pollAction, action);
    // Wait for the stop polling action for this endpoint.
    yield* take(
      (dispatchedAction: AnyAction) =>
        isStopPollingAction(dispatchedAction) &&
        pollRequestId(dispatchedAction) === id
    );
    // Cancel polling.
    yield* cancel(pollingTask);
    // Exit the while loop.
    poll = false;
  }
}
