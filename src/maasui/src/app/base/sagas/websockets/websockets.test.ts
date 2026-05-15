import { eventChannel } from "redux-saga";
import { call, put, take } from "redux-saga/effects";
import { expectSaga } from "redux-saga-test-plan";
import * as matchers from "redux-saga-test-plan/matchers";
import type { Mock } from "vitest";

import {
  handleFileContextRequest,
  storeFileContextActions,
} from "./handlers/file-context-requests";
import { handleNextActions, nextActions } from "./handlers/next-actions";
import { pollAction, handlePolling } from "./handlers/polling-requests";
import { handleUnsubscribe } from "./handlers/unsubscribe";
import type { WebSocketChannel } from "./websockets";
import {
  WEBSOCKET_PING_INTERVAL,
  createConnection,
  handleWebsocketEvent,
  handleNotifyMessage,
  handlePingMessage,
  sendMessage,
  watchWebsocketEvents,
  watchWebSockets,
} from "./websockets";

import type { Config } from "@/app/store/config/types";
import { machineActions } from "@/app/store/machine";
import { getCookie } from "@/app/utils";
import * as factory from "@/testing/factories";
import WebSocketClient, {
  WebSocketMessageType,
  WebSocketResponseType,
} from "@/websocket-client";
import type {
  WebSocketResponseNotify,
  WebSocketResponsePing,
  WebSocketResponseResult,
} from "@/websocket-client";

vi.mock("@/app/utils", async () => {
  const actual: object = await vi.importActual("@/app/utils");
  return {
    ...actual,
    getCookie: vi.fn(),
  };
});

describe("websocket sagas", () => {
  let socketChannel: WebSocketChannel;
  let socketClient: WebSocketClient;
  const getCookieMock = getCookie as Mock;

  beforeEach(() => {
    getCookieMock.mockImplementation(() => "abc123");
    socketClient = new WebSocketClient();
    socketClient.connect();
    if (socketClient.rws) {
      socketClient.rws.onerror = vi.fn();
      socketClient.rws.close = vi.fn();
    }
    socketChannel = eventChannel(() => () => null);
  });

  afterEach(() => {
    vi.resetModules();
  });

  it("connects to a WebSocket", () => {
    return expectSaga(watchWebSockets, socketClient)
      .provide([[call(createConnection, socketClient), {}]])
      .take("status/websocketConnect")
      .put({
        type: "status/websocketConnected",
      })
      .dispatch({
        type: "status/websocketConnect",
      })
      .run();
  });

  it("raises an error if no csrftoken exists", () => {
    const error = new Error(
      "No csrftoken found, please ensure you are logged into MAAS."
    );
    socketClient.rws = null;
    socketClient.buildURL = vi.fn(() => {
      throw error;
    });
    return expectSaga(watchWebSockets, socketClient)
      .take("status/websocketConnect")
      .put({
        type: "status/websocketError",
        error: true,
        payload: error.message,
      })
      .dispatch({
        type: "status/websocketConnect",
      })
      .run();
  });

  it("sends a websocket ping message to keep the connection alive", () => {
    return expectSaga(watchWebSockets, socketClient)
      .dispatch({
        type: "status/websocketConnected",
      })
      .put({
        type: "status/websocketPing",
        meta: {
          poll: true,
          pollInterval: WEBSOCKET_PING_INTERVAL,
          model: "status",
          method: "ping",
        },
      })
      .run();
  });

  it("stops pinging the websocket when disconnected", () => {
    return expectSaga(watchWebSockets, socketClient)
      .dispatch({
        type: "status/websocketDisconnected",
      })
      .put({
        type: "status/websocketPingStop",
        meta: {
          pollStop: true,
          model: "status",
          method: "ping",
        },
      })
      .run();
  });

  it("can create a WebSocket connection", () => {
    expect.assertions(1);
    const socket = createConnection(socketClient);
    if (socketClient.rws?.onopen) {
      socketClient.rws.onopen({} as Event);
    }
    return expect(socket).resolves.toEqual(socketClient);
  });

  it("can watch for WebSocket messages", () => {
    const channel = watchWebsocketEvents(socketClient);
    let response;
    channel.take((val) => (response = val));
    if (socketClient.rws?.onmessage) {
      socketClient.rws.onmessage({
        data: '{"message": "secret"}',
      } as MessageEvent);
    }
    expect(response).toEqual({
      data: '{"message": "secret"}',
    });
  });

  it("closes WebSocket connection when channel is closed", () => {
    const channel = watchWebsocketEvents(socketClient);
    expect(socketClient.rws?.close).not.toHaveBeenCalled();
    channel.close();
    expect(socketClient.rws?.close).toHaveBeenCalled();
  });

  it("can send a WebSocket message", () => {
    const action = {
      type: "machine/action",
      meta: {
        model: "machine",
        method: "action",
        type: WebSocketMessageType.REQUEST,
      },
      payload: {
        params: { foo: "bar" },
      },
    } as const;
    const saga = sendMessage(socketClient, action);
    expect(saga.next().value).toEqual(
      put({ meta: { item: { foo: "bar" } }, type: "machine/actionStart" })
    );
    expect(saga.next().value).toEqual(
      call([socketClient, socketClient.send], action, {
        method: "machine.action",
        type: WebSocketMessageType.REQUEST,
        params: { foo: "bar" },
      })
    );
  });

  it("can send a WebSocket ping message", () => {
    const action = {
      type: "status/websocketPing",
      meta: {
        model: "status",
        method: "ping",
        type: WebSocketMessageType.PING,
      },
      payload: null,
    } as const;
    const saga = sendMessage(socketClient, action);
    expect(saga.next().value).toEqual(
      put({
        meta: { item: null },
        type: "status/websocketPingStart",
      })
    );
    expect(saga.next().value).toEqual(
      call([socketClient, socketClient.send], action, {
        method: "status.ping",
        type: WebSocketMessageType.PING,
      })
    );
  });

  it("can send a WebSocket message with a request id", () => {
    const action = {
      type: "machine/action",
      meta: {
        model: "machine",
        method: "action",
        callId: "123456",
        type: WebSocketMessageType.REQUEST,
      },
      payload: {
        params: { foo: "bar" },
      },
    } as const;
    const saga = sendMessage(socketClient, action);
    expect(saga.next().value).toEqual(
      put({
        meta: { item: { foo: "bar" }, callId: "123456" },
        type: "machine/actionStart",
      })
    );
    expect(saga.next().value).toEqual(
      call([socketClient, socketClient.send], action, {
        method: "machine.action",
        type: WebSocketMessageType.REQUEST,
        params: { foo: "bar" },
      })
    );
  });

  it("can store a next action when sending a WebSocket message", () => {
    const action = {
      type: "machine/action",
      meta: {
        model: "machine",
        method: "action",
        type: WebSocketMessageType.REQUEST,
      },
      payload: {
        params: { foo: "bar" },
      },
    } as const;
    const nextActionCreators = [vi.fn()];
    return expectSaga(sendMessage, socketClient, action, nextActionCreators)
      .provide([[matchers.call.fn(socketClient.send), 808]])
      .call([nextActions, nextActions.set], 808, nextActionCreators)
      .run();
  });

  it("continues if data has already been fetched for list methods", () => {
    const action = {
      type: "machine/fetch",
      meta: {
        model: "machine",
        method: "list",
        type: WebSocketMessageType.REQUEST,
      },
      payload: {
        params: {},
      },
    } as const;
    const previous = sendMessage(socketClient, action);
    previous.next();
    const saga = sendMessage(socketClient, action);
    // The saga should have finished.
    expect(saga.next().done).toBe(true);
  });

  it("continues if data has already been fetched for methods with cache", () => {
    const action = {
      type: "machine/fetch",
      meta: {
        cache: true,
        model: "machine",
        method: "get",
        type: WebSocketMessageType.REQUEST,
      },
      payload: {
        params: {},
      },
    } as const;
    const previous = sendMessage(socketClient, action);
    previous.next();
    const saga = sendMessage(socketClient, action);
    // The saga should have finished.
    expect(saga.next().done).toBe(true);
  });

  it("fetches list methods if no-cache is set", () => {
    const action = {
      type: "machine/fetch",
      meta: {
        model: "machine",
        method: "list",
        type: WebSocketMessageType.REQUEST,
        nocache: true,
      },
      payload: {
        params: {},
      },
    } as const;
    const previous = sendMessage(socketClient, action);
    previous.next();
    const saga = sendMessage(socketClient, action);
    // The saga should not have finished.
    expect(saga.next().done).toBe(false);
  });

  it("can handle dispatching for each param in an array", () => {
    const action = {
      type: "config/update",
      meta: {
        dispatchMultiple: true,
        model: "config",
        method: "update",
        type: WebSocketMessageType.REQUEST,
      },
      payload: {
        params: [
          { name: "foo", value: "bar" },
          { name: "baz", value: "qux" },
        ] as { name: string; value: Config<string>["value"] }[],
      },
    } as const;
    const saga = sendMessage(socketClient, action);
    expect(saga.next().value).toEqual(
      put({
        meta: {
          item: [
            { name: "foo", value: "bar" },
            { name: "baz", value: "qux" },
          ],
        },
        type: "config/updateStart",
      })
    );

    expect(saga.next().value).toEqual(
      call([socketClient, socketClient.send], action, {
        method: "config.update",
        type: WebSocketMessageType.REQUEST,
        params: { name: "foo", value: "bar" },
      })
    );
    expect(saga.next().value).toEqual(take("config/updateNotify"));

    expect(saga.next().value).toEqual(
      call([socketClient, socketClient.send], action, {
        method: "config.update",
        type: WebSocketMessageType.REQUEST,
        params: { name: "baz", value: "qux" },
      })
    );
    expect(saga.next().value).toEqual(take("config/updateNotify"));
  });

  it("can handle errors when sending a WebSocket message", () => {
    const saga = sendMessage(socketClient, {
      type: "machine/action",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: { foo: "bar" },
      },
    });
    saga.next();
    saga.next();
    expect(saga.throw("error!").value).toEqual(
      put({
        error: true,
        meta: { item: { foo: "bar" } },
        type: "machine/actionError",
        payload: "error!",
      })
    );
  });

  it("can handle a WebSocket response message", () => {
    const saga = handleWebsocketEvent(socketChannel, socketClient);
    expect(saga.next().value).toEqual(take(socketChannel));
    expect(
      saga.next({
        data: JSON.stringify({ request_id: 99, result: { response: "here" } }),
      }).value
    ).toStrictEqual(call([socketClient, socketClient.getRequest], 99));
    saga.next({
      type: "machine/action",
      payload: { id: 808 },
      meta: { identifier: 123 },
    });
    expect(saga.next(false).value).toEqual(
      put({
        meta: { item: { id: 808 }, identifier: 123 },
        type: "machine/actionSuccess",
        payload: { response: "here" },
      })
    );
  });

  it("can handle a WebSocket response message with a request id", () => {
    const saga = handleWebsocketEvent(socketChannel, socketClient);
    expect(saga.next().value).toEqual(take(socketChannel));
    expect(
      saga.next({
        data: JSON.stringify({ request_id: 99, result: { response: "here" } }),
      }).value
    ).toStrictEqual(call([socketClient, socketClient.getRequest], 99));
    saga.next({
      type: "machine/action",
      payload: { id: 808 },
      meta: { identifier: 123, callId: "456" },
    });
    expect(saga.next(false).value).toEqual(
      put({
        meta: { item: { id: 808 }, identifier: 123, callId: "456" },
        type: "machine/actionSuccess",
        payload: { response: "here" },
      })
    );
  });

  it("can dispatch a next action", () => {
    const response: WebSocketResponseResult = {
      rtype: WebSocketResponseType.SUCCESS,
      type: WebSocketMessageType.RESPONSE,
      request_id: 99,
      result: { id: 808 },
    };
    const action = { type: "NEXT_ACTION" };
    const actionCreator = vi.fn(() => action);
    return expectSaga(handleNextActions, response)
      .provide([
        [call([nextActions, nextActions.get], 99), [actionCreator]],
        [call([nextActions, nextActions.delete], 99), null],
      ])
      .call(actionCreator, response.result)
      .put(action)
      .run();
  });

  it("can handle a WebSocket error response message", () => {
    const saga = handleWebsocketEvent(socketChannel, socketClient);
    expect(saga.next().value).toEqual(take(socketChannel));
    expect(
      saga.next({
        data: JSON.stringify({
          request_id: 99,
          error: '{"Message": "catastrophic failure"}',
        }),
      }).value
    ).toEqual(call([socketClient, socketClient.getRequest], 99));
    saga.next({ type: "machine/action", payload: { id: 808 } });
    expect(saga.next(false).value).toEqual(
      put({
        error: true,
        meta: {
          item: { id: 808 },
        },
        payload: { Message: "catastrophic failure" },
        type: "machine/actionError",
      })
    );
  });

  it("can handle a WebSocket error message that is not JSON", () => {
    const saga = handleWebsocketEvent(socketChannel, socketClient);
    expect(saga.next().value).toEqual(take(socketChannel));
    expect(
      saga.next({
        data: JSON.stringify({
          request_id: 99,
          error: '("catastrophic failure")',
        }),
      }).value
    ).toEqual(call([socketClient, socketClient.getRequest], 99));
    saga.next({ type: "machine/action", payload: { id: 808 } });
    expect(saga.next(false).value).toEqual(
      put({
        error: true,
        meta: {
          item: { id: 808 },
        },
        payload: '("catastrophic failure")',
        type: "machine/actionError",
      })
    );
  });

  it("can handle a WebSocket ping message", () => {
    const saga = handleWebsocketEvent(socketChannel, socketClient);
    const response: WebSocketResponsePing = {
      request_id: 1,
      result: 1,
      rtype: 0,
      type: WebSocketMessageType.PING_REPLY,
    };
    expect(saga.next().value).toEqual(take(socketChannel));
    expect(saga.next({ data: JSON.stringify(response) }).value).toEqual(
      call(handlePingMessage, response)
    );
    expect(saga.next().value).toEqual(take(socketChannel));
  });

  it("can handle a WebSocket notify message", () => {
    const saga = handleWebsocketEvent(socketChannel, socketClient);
    const response: WebSocketResponseNotify = {
      type: WebSocketMessageType.NOTIFY,
      name: "config",
      action: "update",
      data: { name: "foo", value: "bar" },
    };
    expect(saga.next().value).toEqual(take(socketChannel));
    expect(saga.next({ data: JSON.stringify(response) }).value).toEqual(
      call(handleNotifyMessage, response)
    );
    // yield no further, take a new message
    expect(saga.next().value).toEqual(take(socketChannel));
  });

  it("can handle a WebSocket close message", () => {
    const saga = handleWebsocketEvent(socketChannel, socketClient);
    expect(saga.next().value).toEqual(take(socketChannel));
    expect(
      saga.next({
        type: "close",
        code: 1000,
        reason: "Session expired",
      }).value
    ).toEqual(
      put({
        type: "status/websocketDisconnect",
        payload: { code: 1000, reason: "Session expired" },
      })
    );
  });

  it("can handle a WebSocket error message", () => {
    const saga = handleWebsocketEvent(socketChannel, socketClient);
    expect(saga.next().value).toEqual(take(socketChannel));
    expect(saga.next({ type: "error", message: "Timeout" }).value).toEqual(
      put({ type: "status/websocketError", error: true, payload: "Timeout" })
    );
  });

  it("can handle a WebSocket open message", () => {
    const saga = handleWebsocketEvent(socketChannel, socketClient);
    expect(saga.next().value).toEqual(take(socketChannel));
    expect(saga.next({ type: "open" }).value).toEqual(
      put({ type: "status/websocketConnect" })
    );
  });

  it("can store a file context action when sending a WebSocket message", () => {
    const action = {
      type: "controller/get_summary_xml",
      meta: {
        fileContextKey: "file1",
        method: "get_summary_xml",
        model: "controller",
        type: WebSocketMessageType.REQUEST,
        useFileContext: true,
      },
      payload: {
        params: { system_id: "abc123" },
      },
    } as const;
    return expectSaga(sendMessage, socketClient, action)
      .provide([[matchers.call.fn(socketClient.send), "abc123"]])
      .call(storeFileContextActions, action, ["abc123"])
      .run();
  });

  it("can handle a file response", () => {
    const saga = handleWebsocketEvent(socketChannel, socketClient);
    saga.next();
    const response: WebSocketResponseResult<string> = {
      request_id: 99,
      rtype: WebSocketResponseType.SUCCESS,
      type: WebSocketMessageType.RESPONSE,
      result: "file contents",
    };
    saga.next({ data: JSON.stringify(response) });
    expect(saga.next().value).toEqual(call(handleFileContextRequest, response));
  });

  it("file responses do not dispatch the payload", () => {
    const saga = handleWebsocketEvent(socketChannel, socketClient);
    saga.next();
    saga.next({
      data: JSON.stringify({
        request_id: 99,
        result: "file contents",
      }),
    });
    saga.next({
      type: "machine/action",
      meta: {
        fileContextKey: "file1",
        method: "action",
        model: "machine",
        type: WebSocketMessageType.REQUEST,
        useFileContext: true,
      },
      payload: {
        params: { system_id: "abc123" },
      },
    });
    expect(saga.next(true).value).toEqual(
      put({
        meta: { item: { system_id: "abc123" } },
        type: "machine/actionSuccess",
        payload: null,
      })
    );
  });

  it("can unsubscribe from unused machines", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        lists: {
          123456: factory.machineStateList({
            groups: [
              factory.machineStateListGroup({
                items: ["abc123"],
              }),
            ],
          }),
        },
      }),
    });
    return expectSaga(
      handleUnsubscribe,
      // @ts-expect-error we're not using the action, just the type
      machineActions.cleanupRequest("123456")
    )
      .withState(state)
      .put(machineActions.unsubscribe(["abc123"]))
      .put(machineActions.removeRequest("123456"))
      .run();
  });

  it("removes request when machines are in use", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        lists: {
          123456: factory.machineStateList({
            groups: [
              factory.machineStateListGroup({
                items: ["abc123"],
              }),
            ],
          }),
        },
      }),
    });
    return expectSaga(
      handleUnsubscribe,
      // @ts-expect-error we're not using the action, just the type
      machineActions.cleanupRequest("123456")
    )
      .withState(state)
      .put(machineActions.removeRequest("123456"))
      .run();
  });

  describe("polling", () => {
    it("can start polling", () => {
      const action = {
        type: "testAction",
        meta: {
          model: "machine",
          method: "action",
          poll: true,
        },
        payload: {
          params: {},
        },
      } as const;
      return expectSaga(handlePolling, action)
        .put({
          type: "testActionPollingStarted",
          meta: { pollId: undefined },
        })
        .run();
    });

    it("can stop polling", () => {
      const action = {
        type: "testAction",
        meta: {
          model: "machine",
          method: "action",
          pollStop: true,
        },
        payload: {
          params: {},
        },
      } as const;
      return expectSaga(handlePolling, action)
        .put({
          type: "testActionPollingStopped",
          meta: { pollId: undefined },
        })
        .dispatch({
          type: "testAction",
          meta: {
            model: "machine",
            method: "action",
            pollStop: true,
          },
          payload: null,
        })
        .run();
    });

    it("can start polling with an id", () => {
      const action = {
        type: "testAction",
        meta: {
          model: "machine",
          method: "action",
          poll: true,
          pollId: "poll123",
        },
        payload: {
          params: {},
        },
      } as const;
      return expectSaga(handlePolling, action)
        .put({
          type: "testActionPollingStarted",
          meta: { pollId: "poll123" },
        })
        .run();
    });

    it("can stop polling with an id", () => {
      const action = {
        type: "testAction",
        meta: {
          model: "machine",
          method: "action",
          pollStop: true,
          pollId: "poll123",
        },
        payload: {
          params: {},
        },
      } as const;
      return expectSaga(handlePolling, action)
        .put({
          type: "testActionPollingStopped",
          meta: { pollId: "poll123" },
        })
        .dispatch({
          type: "testAction",
          meta: {
            model: "machine",
            method: "action",
            pollStop: true,
            pollId: "poll123",
          },
        })
        .run();
    });

    it("sends the action after the interval", () => {
      const action = {
        type: "machine/list",
        meta: {
          model: "machine",
          method: "list",
          poll: true,
        },
        payload: {
          params: {},
        },
      } as const;
      const saga = pollAction(action);
      // Skip the delay:
      saga.next();
      expect(saga.next(action).value).toEqual(put(action));
    });
  });
});
