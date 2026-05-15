import { useEffect } from "react";

import { useSelector } from "react-redux";

import type { useExtendSession } from "@/app/api/query/auth";
import status from "@/app/store/status/selectors";

const useSessionExtender = (
  extendSession: ReturnType<typeof useExtendSession>
) => {
  const authenticated = useSelector(status.authenticated);

  useEffect(() => {
    if (!authenticated) {
      return;
    }
    const interval = setInterval(() => {
      extendSession.mutate({});
    }, 60000);
    return () => {
      clearInterval(interval);
    };
  }, [authenticated, extendSession]);
};

export default useSessionExtender;
