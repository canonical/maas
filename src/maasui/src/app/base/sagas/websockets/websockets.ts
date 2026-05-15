import * as Sentry from "@sentry/browser";
import type {
  Event as ReconnectingWebSocketEvent,
  ErrorEvent,
  CloseEvent,
} from "reconnecting-websocket";
import type { Action, AnyAction } from "redux";
import type { EventChannel } from "redux-saga";
import { eventChannel } from "redux-saga";
import {
  all,
  call,
  put,
  take,
  takeEvery,
  takeLatest,
  race,
} from "typed-redux-saga";
import type { SagaGenerator } from "typed-redux-saga/macro";

import {
  handleFileContextRequest,
  storeFileContextActions,
} from "./handlers/file-context-requests";
import { isLoaded, resetLoaded, setLoaded } from "./handlers/loaded-endpoints";
import {
  handlePolling,
  isStartPollingAction,
  isStopPollingAction,
} from "./handlers/polling-requests";

import type {
  MessageHandler,
  NextActionCreator,
} from "@/app/base/sagas/actions";
import {
  handleNextActions,
  storeNextActions,
} from "@/app/base/sagas/websockets/handlers/next-actions";
import {
  handleUnsubscribe,
  isUnsubscribeAction,
} from "@/app/base/sagas/websockets/handlers/unsubscribe";
import type { GenericMeta } from "@/app/store/utils/slice";
import { WebSocketMessageType } from "@/websocket-client";
import type {
  WebSocketAction,
  WebSocketClient,
  WebSocketRequestMessage,
  WebSocketActionParams,
  WebSocketResponseNotify,
  WebSocketResponsePing,
  WebSocketEndpoint,
} from "@/websocket-client";

export type WebSocketChannel = EventChannel<
  | CloseEvent
  | ErrorEvent
  // The reponse from the websocket API will be a JSON string.
  | MessageEvent<string>
  | ReconnectingWebSocketEvent
>;

/**
 * An action containing an RPC method is a websocket request action.
 * @param {Object} action.
 * @returns {Bool} - action is a request action.
 */
export const isWebsocketRequestAction = (action: AnyAction): boolean =>
  Boolean(action?.meta?.method && action?.meta?.model) &&
  // Ignore actions that are for stopping the polling action.
  !isStopPollingAction(action);

/**
 * Handle incoming notify messages.
 *
 * Notify messages have an action and a payload:
 * {"type": 2,
 *  "name": "config",
 *  "action": "update",
 *  "data": {"name": "maas_name", "value": "maas-hysteria"}}
 *
 * Although we receive a corresponding response for each websocket requests,
 * in some cases the store is only updated once a notify message has been received.
 */
export function* handleNotifyMessage({
  action,
  data,
  name,
}: WebSocketResponseNotify): SagaGenerator<void> {
  yield* put({
    type: `${name}/${action}Notify`,
    payload: data,
  });
}

/**
 * Handle incoming ping response messages.
 *
 */
export function* handlePingMessage({
  result,
}: WebSocketResponsePing): SagaGenerator<void> {
  yield* put({
    type: "status/websocketPingReply",
    payload: result,
  });
}

/**
 * Create a WebSocket connection via the client.
 */
export function createConnection(
  websocketClient: WebSocketClient
): Promise<WebSocketClient> {
  // As the socket automatically tries to reconnect we don't reject this
  // promise, but rather wait for it to eventually connect.
  return new Promise((resolve, reject) => {
    const readyState = websocketClient.rws?.readyState;
    const closedOrClosing: readonly number[] = [
      WebSocket.CLOSED,
      WebSocket.CLOSING,
    ] as const;
    if (readyState === WebSocket.OPEN) {
      resolve(websocketClient);
      return;
    } else if (
      !websocketClient.rws ||
      (readyState && closedOrClosing.includes(readyState))
    ) {
      try {
        // Check that the csrftoken etc. exist to create the connection. The
        // check is done here because we don't want to reject errors when
        // connecting so that the reconnecting websocket can keep trying.
        websocketClient.buildURL();
      } catch (error) {
        reject(error);
      }
      websocketClient.connect();
    }
    if (websocketClient.rws) {
      websocketClient.rws.onopen = () => {
        resolve(websocketClient);
      };
    }
  });
}

/**
 * Create a channel to handle WebSocket messages.
 */
export function watchWebsocketEvents(
  socketClient: WebSocketClient
): WebSocketChannel {
  return eventChannel((emit) => {
    if (socketClient.rws) {
      socketClient.rws.onmessage = (event) => {
        emit(event);
      };
      socketClient.rws.onopen = (event) => {
        emit(event);
      };
      socketClient.rws.onerror = (event) => {
        emit(event);
      };
      socketClient.rws.onclose = (event) => {
        emit(event);
      };
    }
    return () => {
      socketClient.rws?.close();
    };
  });
}

/**
 * Handle messages received over the WebSocket.
 */
export function* handleWebsocketEvent(
  socketChannel: WebSocketChannel,
  socketClient: WebSocketClient
): SagaGenerator<void> {
  while (true) {
    const websocketEvent = yield* take(socketChannel);

    switch (websocketEvent.type) {
      case "error": {
        Sentry.withScope((scope) => {
          scope.setExtras({
            wsRequestsSize: socketClient._requests.size,
            rwsRetryCount: socketClient.rws?.retryCount,
          });
          scope.setTag("action", "status/websocketError");
          Sentry.captureException(websocketEvent);
        });
        if ("message" in websocketEvent) {
          yield* put({
            error: true,
            payload: websocketEvent.message,
            type: "status/websocketError",
          });
        }
        break;
      }

      case "close": {
        const { code, reason } = websocketEvent as CloseEvent;
        yield* put({
          type: "status/websocketDisconnect",
          payload: { code, reason },
        });
        break;
      }

      case "open": {
        yield* put({ type: "status/websocketConnect" });
        resetLoaded();
        break;
      }

      case "message":
      default: {
        if ("data" in websocketEvent) {
          const response = JSON.parse(websocketEvent.data);

          switch (response.type) {
            case WebSocketMessageType.PING_REPLY: {
              yield* call(handlePingMessage, response);
              break;
            }
            case WebSocketMessageType.NOTIFY: {
              yield* call(handleNotifyMessage, response);
              break;
            }
            case WebSocketMessageType.RESPONSE:
            default: {
              // This is a response message, fetch the corresponding action for the
              // message that was sent.
              const action = yield* call(
                [socketClient, socketClient.getRequest],
                response.request_id
              );

              // Handle file context requests, if required.
              const isFileContextRequest = yield* call(
                handleFileContextRequest,
                response
              );
              if (!action) {
                return;
              }
              // Depending on the action the parameters might be contained in the
              // `params` parameter.
              const item = action.payload?.params || action.payload;
              let error;
              let result;
              if (response.error) {
                try {
                  error = JSON.parse(response.error);
                } catch {
                  error = response.error;
                }
              } else {
                // If this uses the file context then don't dispatch the response
                // payload.
                result = isFileContextRequest ? null : response.result;
              }
              // Sometimes the error response is the original payload sent back, which
              // can be 0 when requesting a model with an id of 0.
              if (error || error === 0) {
                yield* put({
                  meta: {
                    item,
                    identifier: action.meta?.identifier,
                    callId: action.meta?.callId,
                  },
                  type: `${action.type}Error`,
                  error: true,
                  payload: error,
                });
              } else {
                yield* put({
                  meta: {
                    item,
                    identifier: action.meta?.identifier,
                    callId: action.meta?.callId,
                  },
                  type: `${action.type}Success`,
                  payload: result,
                });
                // Handle dispatching next actions, if required.
                yield* call(handleNextActions, response);
              }
              break;
            }
          }
        }
      }
    }
  }
}

/**
 * Build a message for websocket requests.
 * @param {Object} meta - action meta object.
 * @param {Object} params - param object (optional).
 * @returns {Object} message - serialisable websocket message.
 */
const buildMessage = (
  meta: WebSocketAction["meta"],
  params?: WebSocketActionParams | null
) => {
  const message: WebSocketRequestMessage = {
    method: `${meta.model}.${meta.method}`,
    // type is always request, except for ping messages
    type:
      meta.model === "status" && meta.method === "ping"
        ? WebSocketMessageType.PING
        : WebSocketMessageType.REQUEST,
  };
  const hasMultipleDispatches = meta.dispatchMultiple && Array.isArray(params);
  if (params && !hasMultipleDispatches) {
    message.params = params;
  }
  return message;
};

/**
 * Send WebSocket messages via the client.
 */
export function* sendMessage(
  socketClient: WebSocketClient,
  action: WebSocketAction,
  nextActionCreators?: NextActionCreator[]
): SagaGenerator<void> {
  const { meta, payload, type } = action;
  const params = payload ? payload.params : null;
  const { cache, identifier, method, model, nocache, callId } = meta;
  const endpoint: WebSocketEndpoint = `${model}.${method}`;
  const hasMultipleDispatches = meta.dispatchMultiple && Array.isArray(params);
  // If method is 'list' and data has loaded/is loading, do not fetch again
  // unless 'nocache' is specified.
  if (
    cache ||
    (method?.endsWith("list") &&
      (!params ||
        hasMultipleDispatches ||
        (!Array.isArray(params) && !params.start)) &&
      !nocache)
  ) {
    if (isLoaded(endpoint)) {
      return;
    }
    setLoaded(endpoint);
  }
  yield* put<Action & { meta: GenericMeta }>({
    meta: {
      item: params || payload,
      identifier,
      callId,
    },
    type: `${type}Start`,
  });
  const requestIDs = [];
  try {
    if (params && hasMultipleDispatches) {
      // We deliberately do not * in parallel here with 'all'
      // to avoid races for dependant config.
      for (const param of params) {
        const id = yield* call(
          [socketClient, socketClient.send],
          action,
          buildMessage(meta, param)
        );
        requestIDs.push(id);
        // Ensure server has synced before sending next message,
        // important for dependant config like commissioning_distro_series
        // and default_min_hwe_kernel.
        // There is an edge case where a different CLI or server event could
        // dispatch a NOTIFY of the same type which is received before our expected NOTIFY,
        // but this _probably_ does not matter in practice.
        yield* take(`${type}Notify`);
      }
    } else {
      const id = yield* call(
        [socketClient, socketClient.send],
        action,
        buildMessage(meta, params)
      );
      requestIDs.push(id);
    }
    // Store the actions to dispatch when the response is received.
    yield* call(storeNextActions, requestIDs, nextActionCreators);
    // Store the actions that need to use the file context.
    yield* call(storeFileContextActions, action, requestIDs);
  } catch (error) {
    yield* put({
      meta: { item: params || payload },
      type: `${type}Error`,
      error: true,
      payload: error,
    });
  }
}

/**
 * Set up a WebSocket connection and start listening for messages from the server.
 * @param {Array} messageHandlers - Sagas that should handle specific messages
 * via the websocket channel.
 */
export function* setupWebSocket({
  websocketClient,
  messageHandlers = [],
}: {
  websocketClient: WebSocketClient;
  messageHandlers?: MessageHandler[];
}): SagaGenerator<void> {
  let socketClient: WebSocketClient;
  try {
    socketClient = yield* call(createConnection, websocketClient);
    yield* put({ type: "status/websocketConnected" });
    // Set up the list of models that have been loaded.
    resetLoaded();
    const socketChannel = yield* call(watchWebsocketEvents, socketClient);
    while (true) {
      const { cancel } = yield* race({
        task: all(
          [
            call(handleWebsocketEvent, socketChannel, socketClient),
            // Using takeEvery() instead of call() here to get around this issue:
            // https://github.com/canonical/maas-ui/issues/172
            takeEvery<
              WebSocketAction,
              (socketClient: WebSocketClient, action: WebSocketAction) => void
            >(isWebsocketRequestAction, sendMessage, socketClient),
            // Take actions that should start polling.
            takeEvery<WebSocketAction, (action: WebSocketAction) => void>(
              isStartPollingAction,
              handlePolling
            ),
            // Take actions that should unsubscribe from entities.
            takeEvery<WebSocketAction, (action: WebSocketAction) => void>(
              isUnsubscribeAction,
              handleUnsubscribe
            ),
          ].concat(
            // Attach the additional actions that should be taken by the
            // websocket channel.
            messageHandlers.map(({ action, method }) =>
              takeEvery(action, method, socketClient, sendMessage)
            )
          )
        ),
        cancel: take("status/websocketDisconnect"),
      });
      if (cancel) {
        yield* put({ type: "status/websocketDisconnected" });
      }
    }
  } catch (error) {
    Sentry.withScope((scope) => {
      scope.setTag("action", "status/websocketError");
      Sentry.captureException(error);
    });
    yield* put({
      type: "status/websocketError",
      error: true,
      payload: error instanceof Error ? error.message : error,
    });
  }
}

/**
 * Send a ping message to the server every 50 seconds to keep the connection alive.
 *
 **/
export const WEBSOCKET_PING_INTERVAL = 50 * 1000; // 50 seconds
function* handleWebsocketPing() {
  yield* put({
    type: "status/websocketPing",
    meta: {
      poll: true,
      pollInterval: WEBSOCKET_PING_INTERVAL,
      model: "status",
      method: "ping",
    },
  });
}
function* handleWebsocketPingStop() {
  yield* put({
    type: "status/websocketPingStop",
    meta: {
      pollStop: true,
      model: "status",
      method: "ping",
    },
  });
}

/**
 * Set up websocket connection on request via status/websocketConnect action
 * @param {Array} messageHandlers - Additional sagas to be handled by the
 * websocket channel.
 */
export function* watchWebSockets(
  websocketClient: WebSocketClient,
  messageHandlers?: MessageHandler[]
): SagaGenerator<void> {
  yield* takeLatest("status/websocketConnect", setupWebSocket, {
    websocketClient,
    messageHandlers,
  });
  yield* takeLatest("status/websocketConnected", handleWebsocketPing);
  yield* takeLatest("status/websocketDisconnected", handleWebsocketPingStop);
}
