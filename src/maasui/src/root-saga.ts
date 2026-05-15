import { all } from "typed-redux-saga";
import type { SagaGenerator } from "typed-redux-saga/macro";

import {
  actionHandlers,
  watchCheckAuthenticated,
  watchLogin,
  watchLogout,
  watchExternalLogin,
  watchWebSockets,
  watchCreateLicenseKey,
  watchUpdateLicenseKey,
  watchDeleteLicenseKey,
  watchFetchLicenseKeys,
  watchUploadScript,
  watchAddMachineChassis,
} from "./app/base/sagas";

import type { MessageHandler } from "@/app/base/sagas/actions";
import type WebSocketClient from "@/websocket-client";

export default function* rootSaga(
  websocketClient: WebSocketClient
): SagaGenerator<void> {
  yield* all([
    watchCheckAuthenticated(),
    watchLogin(),
    watchLogout(),
    watchExternalLogin(),
    watchWebSockets(websocketClient, actionHandlers as MessageHandler[]),
    watchCreateLicenseKey(),
    watchUpdateLicenseKey(),
    watchDeleteLicenseKey(),
    watchFetchLicenseKeys(),
    watchUploadScript(),
    watchAddMachineChassis(),
  ]);
}
