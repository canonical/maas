import { StrictMode } from "react";

import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { createRoot } from "react-dom/client";
import { Provider } from "react-redux";
import { RouterProvider } from "react-router";

import packageInfo from "../package.json";

import { configureAuthInterceptor } from "./app/api/auth-interceptor";
import { createQueryClient } from "./app/api/query-client";
import useDarkMode from "./app/base/hooks/useDarkMode/useDarkMode";
import { store } from "./redux-store";

import NewSidePanelContextProvider from "@/app/base/side-panel-context";
import { WebSocketProvider } from "@/app/base/websocket-context";
import { router } from "@/router";
import "./scss/index.scss";

configureAuthInterceptor();

export const Root = () => {
  const queryClient = createQueryClient();

  return (
    <Provider store={store}>
      <WebSocketProvider>
        <QueryClientProvider client={queryClient}>
          <NewSidePanelContextProvider>
            <RouterProvider router={router} />
          </NewSidePanelContextProvider>
          <ReactQueryDevtools
            buttonPosition="bottom-left"
            initialIsOpen={
              import.meta.env.VITE_APP_REACT_QUERY_DEVTOOLS === "true"
            }
          />
        </QueryClientProvider>
      </WebSocketProvider>
    </Provider>
  );
};

const AppRoot = (): React.ReactElement => {
  useDarkMode();

  return (
    <StrictMode>
      <Root />
    </StrictMode>
  );
};

const container = document.getElementById("root");

if (container) {
  const root = createRoot(container);
  root.render(<AppRoot />);
}

// log the maas-ui version to the console
// eslint-disable-next-line no-console
console.info(
  `${packageInfo.name} ${packageInfo.version} ${
    import.meta.env.VITE_APP_GIT_SHA ?? ""
  }`
);

export default AppRoot;
