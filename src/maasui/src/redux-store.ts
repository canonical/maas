import { configureStore } from "@reduxjs/toolkit";
import { createBrowserHistory } from "history";
import { createReduxHistoryContext } from "redux-first-history";
import createSagaMiddleware from "redux-saga";

import createRootReducer from "./root-reducer";
import rootSaga from "./root-saga";
import WebSocketClient from "./websocket-client";

const { createReduxHistory, routerMiddleware, routerReducer } =
  createReduxHistoryContext({
    history: createBrowserHistory(),
  });

const reducer = createRootReducer(routerReducer);

const sagaMiddleware = createSagaMiddleware();
const checkMiddleware = import.meta.env.VITE_APP_CHECK_MIDDLEWARE === "true";

export const store = configureStore({
  reducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      thunk: false,
      immutableCheck: checkMiddleware,
      serializableCheck: checkMiddleware,
    }).concat(sagaMiddleware, routerMiddleware),
  devTools: import.meta.env.NODE_ENV !== "production",
});
export const history = createReduxHistory(store);

export const websocketClient = new WebSocketClient();

sagaMiddleware.run(rootSaga, websocketClient);
