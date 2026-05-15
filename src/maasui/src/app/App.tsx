import type { ReactNode } from "react";
import { Suspense, useEffect } from "react";

import {
  Application,
  AppStatus,
  Notification as NotificationBanner,
  NotificationProvider,
  ToastNotificationProvider,
} from "@canonical/react-components";
import { usePrevious } from "@canonical/react-components/dist/hooks";
import * as Sentry from "@sentry/browser";
import { useDispatch, useSelector } from "react-redux";
import { Outlet, useLocation } from "react-router";

import packageInfo from "../../package.json";

import { useCreateSession, useExtendSession } from "./api/query/auth";
import {
  useDismissNotification,
  useDismissNotifications,
} from "./api/query/notifications";
import PageContent from "./base/components/PageContent/PageContent";
import SectionHeader from "./base/components/SectionHeader";
import useSessionExtender from "./base/hooks/useSessionExtender/useSessionExtender";
import ThemePreviewContextProvider from "./base/theme-context";
import { MAAS_UI_ID } from "./constants";
import { getCookie } from "./utils";

import AppSideNavigation from "@/app/base/components/AppSideNavigation";
import StatusBar from "@/app/base/components/StatusBar";
import FileContext, { fileContextStore } from "@/app/base/file-context";
import { useFetchActions } from "@/app/base/hooks";
import { configActions } from "@/app/store/config";
import configSelectors from "@/app/store/config/selectors";
import { generalActions } from "@/app/store/general";
import { statusActions } from "@/app/store/status";
import status from "@/app/store/status/selectors";

export enum VaultErrors {
  REQUEST_FAILED = "Vault request failed",
  CONNECTION_FAILED = "Vault connection failed",
}

const ConnectionStatus = () => {
  const connected = useSelector(status.connected);
  const connectedCount = useSelector(status.connectedCount);
  const connecting = useSelector(status.connecting);
  const connectionError = useSelector(status.error);
  const authenticated = useSelector(status.authenticated);
  const shouldDisplayConnectionError =
    connectedCount > 0 &&
    authenticated &&
    (!!connectionError || (!connecting && !connected));

  useEffect(() => {
    if (connectionError) {
      Sentry.captureMessage(
        `Connection Error: ${connectionError}`,
        "warning" // Sentry.Severity.Warning is deprecated
      );
    }
  }, [connectionError]);

  return shouldDisplayConnectionError ? (
    <div className="p-modal" style={{ alignItems: "flex-start" }}>
      <section
        className="p-modal__dialog"
        style={{
          paddingTop: "1rem",
          paddingLeft: "2rem",
          paddingRight: "2rem",
        }}
      >
        <h5 className="u-no-margin--bottom u-no-padding--top">
          Trying to reconnect...
        </h5>
      </section>
    </div>
  ) : null;
};

export const App = (): React.ReactElement => {
  const dispatch = useDispatch();
  const analyticsEnabled = useSelector(configSelectors.analyticsEnabled);
  const authenticated = useSelector(status.authenticated);
  const createSession = useCreateSession();
  const authenticating = useSelector(status.authenticating);
  const connected = useSelector(status.connected);
  const connecting = useSelector(status.connecting);
  const configLoading = useSelector(configSelectors.loading);
  const configErrors = useSelector(configSelectors.errors);
  const extendSession = useExtendSession();
  const previousAuthenticated = usePrevious(authenticated, false);
  const dismissMutation = useDismissNotification();
  const location = useLocation();
  const dismiss = useDismissNotifications(dismissMutation.mutate);

  useSessionExtender(extendSession);
  useFetchActions([statusActions.checkAuthenticated]);

  useEffect(() => {
    // Needs to be fetched again to know if external auth is being used.
    if (previousAuthenticated && !authenticated) {
      dispatch(statusActions.checkAuthenticated());
    }
  }, [authenticated, dispatch, previousAuthenticated]);

  useEffect(() => {
    const initializeSession = async () => {
      if (authenticated) {
        // If the user is authenticated but has no session cookies,
        // create a new session so that the websocket connection can be established.
        const csrftoken = getCookie("csrftoken");
        const sessionid = getCookie("sessionid");
        if (!csrftoken || !sessionid) {
          await createSession.mutateAsync({});
        }

        // Connect the websocket before anything else in the app can be done.
        dispatch(statusActions.websocketConnect());
      }
    };
    initializeSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch, authenticated]);

  useEffect(() => {
    if (connected) {
      dispatch(generalActions.fetchVersion());
      // Fetch the config at the top so we can access the MAAS name for the
      // window title.
      dispatch(configActions.fetch());
    }
  }, [dispatch, connected]);
  const isLoading =
    authenticating || configLoading || (!connected && connecting);
  const hasVaultError =
    configErrors === VaultErrors.REQUEST_FAILED ||
    configErrors === VaultErrors.CONNECTION_FAILED;

  let content: ReactNode;
  // display loading spinner only on initial load
  // this prevents flashing of the loading screen when websocket connection is lost and restored
  if (isLoading) {
    content = <PageContent header={<SectionHeader loading />} />;
  } else if (hasVaultError) {
    content = (
      <PageContent header={<SectionHeader title="Failed to connect" />}>
        <NotificationBanner severity="negative" title="Error:">
          The server connection failed with the error "{configErrors}"
        </NotificationBanner>
      </PageContent>
    );
  } else {
    content = (
      <FileContext.Provider value={fileContextStore}>
        <Outlet />
      </FileContext.Provider>
    );
  }

  if (analyticsEnabled && import.meta.env.VITE_APP_SENTRY_DSN) {
    Sentry.init({
      dsn: import.meta.env.VITE_APP_SENTRY_DSN,
      release: packageInfo.version,
    });
  }

  return (
    <Application id={MAAS_UI_ID}>
      <ThemePreviewContextProvider>
        <ToastNotificationProvider onDismiss={dismiss}>
          <NotificationProvider pathname={location.pathname}>
            <ConnectionStatus />
            <AppSideNavigation />

            <Suspense
              fallback={<PageContent header={<SectionHeader loading />} />}
            >
              {content}
            </Suspense>
            {authenticated && (
              <AppStatus>
                <StatusBar />
              </AppStatus>
            )}
          </NotificationProvider>
        </ToastNotificationProvider>
      </ThemePreviewContextProvider>
    </Application>
  );
};

export default App;
