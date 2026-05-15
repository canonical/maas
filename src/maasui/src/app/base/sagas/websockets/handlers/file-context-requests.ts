import type { SagaGenerator } from "typed-redux-saga";
import { call } from "typed-redux-saga";

import { fileContextStore } from "@/app/base/file-context";
import type {
  WebSocketAction,
  WebSocketRequest,
  WebSocketResponseResult,
} from "@/websocket-client";

// A store of websocket requests that need to store their responses in the file
// context. The map is between request id and redux action object.
export const fileContextRequests = new Map<
  WebSocketRequest["request_id"],
  WebSocketAction
>();

/**
 * Store the actions that need to store files in the file context.
 *
 * @param {Object} action - A Redux action.
 * @param {Array} requestIDs - A list of ids for the requests associated with
 * this action.
 */
export function storeFileContextActions(
  action: WebSocketAction,
  requestIDs: WebSocketRequest["request_id"][]
): void {
  if (action?.meta?.useFileContext) {
    requestIDs.forEach((id) => {
      fileContextRequests.set(id, action);
    });
  }
}

/**
 * Handle storing a file in the file context store, if required.
 *
 * @param {Object} response - A websocket response.
 */
export function* handleFileContextRequest({
  request_id,
  result,
}: WebSocketResponseResult<string>): SagaGenerator<boolean> {
  const fileContextRequest = yield* call(
    [fileContextRequests, fileContextRequests.get],
    request_id
  );
  if (fileContextRequest?.meta.fileContextKey) {
    // Store the file in the context.
    fileContextStore.add(fileContextRequest?.meta.fileContextKey, result);
    // Clean up the previous request.
    fileContextRequests.delete(request_id);
  }
  return !!fileContextRequest;
}
