import { useDispatch } from "react-redux";

import { resetSilentPolling } from "@/app/images/hooks/useOptimisticImages/utils/silentPolling";
import { statusActions } from "@/app/store/status";
import { clearCookie } from "@/app/utils";
import { COOKIE_NAMES } from "@/app/utils/cookies";

export const useLogout = () => {
  const dispatch = useDispatch();

  return () => {
    resetSilentPolling();
    localStorage.removeItem("maas-config");
    clearCookie(COOKIE_NAMES.LOCAL_JWT_TOKEN_NAME, {
      path: "/",
    });
    clearCookie(COOKIE_NAMES.LOCAL_REFRESH_TOKEN_NAME, {
      path: "/",
    });
    dispatch(statusActions.logout());
  };
};
