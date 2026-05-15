import { useEffect } from "react";

import { useSelector } from "react-redux";
import {
  createSearchParams,
  Outlet,
  useLocation,
  useMatch,
  useNavigate,
} from "react-router";

import { useGetCurrentUser } from "@/app/api/query/auth";
import { useCompletedIntro, useCompletedUserIntro } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import configSelectors from "@/app/store/config/selectors";
import status from "@/app/store/status/selectors";

const RequireLogin = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const authenticating = useSelector(status.authenticating);
  const authenticated = useSelector(status.authenticated);
  const connected = useSelector(status.connected);
  const connecting = useSelector(status.connecting);
  const connectionError = useSelector(status.error);
  const user = useGetCurrentUser();
  const completedIntro = useCompletedIntro();
  const completedUserIntro = useCompletedUserIntro();
  const isAuthenticated = !!user.data;
  const introMatch = useMatch({ path: urls.intro.index, end: false });
  const isAtIntro = !!introMatch;
  const configLoaded = useSelector(configSelectors.loaded);

  const isLoading =
    user.isPending || authenticating || (!connected && connecting);
  const hasAuthError = !authenticated && !connectionError;

  useEffect(() => {
    if (!isLoading && hasAuthError) {
      navigate({
        pathname: urls.login,
        search: `?${createSearchParams({ redirectTo: location.pathname })}`,
      });
    }
  }, [hasAuthError, isLoading, location, navigate]);

  // Redirect to the intro pages if not completed.
  useEffect(() => {
    // Check that we're not already at the intro to allow navigation through the
    // intro pages. This is necessary beacuse this useEffect runs every time
    // there is a navigation change as the `navigate` function is regenerated
    // for every route change, see:
    // https://github.com/remix-run/react-router/issues/7634
    if (!isAtIntro && !isLoading && configLoaded) {
      if (hasAuthError) {
        navigate({
          pathname: urls.login,
          search: `?${createSearchParams({ redirectTo: location.pathname })}`,
        });
      } else if (!completedIntro) {
        navigate({ pathname: urls.intro.index }, { replace: true });
      } else if (isAuthenticated && !completedUserIntro) {
        navigate({ pathname: urls.intro.user }, { replace: true });
      }
    }
  }, [
    completedIntro,
    completedUserIntro,
    configLoaded,
    isLoading,
    isAtIntro,
    isAuthenticated,
    navigate,
    hasAuthError,
    location.pathname,
  ]);

  if (!authenticated) {
    return null;
  }

  return <Outlet />;
};

export default RequireLogin;
