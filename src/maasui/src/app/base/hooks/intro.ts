import { useSelector } from "react-redux";

import { useGetCurrentUser } from "@/app/api/query/auth";
import configSelectors from "@/app/store/config/selectors";
import { getCookie } from "@/app/utils";

/**
 * Returns whether the initial setup intro has been completed or skipped.
 */
export const useCompletedIntro = (): boolean => {
  const completedIntro = useSelector(configSelectors.completedIntro);
  const completedIntroCookie = getCookie("skipsetupintro");
  if (completedIntroCookie) {
    if (completedIntroCookie === "false") {
      return false;
    } else if (completedIntroCookie === "true") {
      return true;
    }
  }
  return !!completedIntro;
};

/**
 * Returns whether the user intro has been completed or skipped.
 */
export const useCompletedUserIntro = (): boolean => {
  const user = useGetCurrentUser();
  const completedUserIntroCookie = getCookie("skipintro");
  if (completedUserIntroCookie) {
    if (completedUserIntroCookie === "false") {
      return false;
    } else if (completedUserIntroCookie === "true") {
      return true;
    }
  }
  return !!user.data?.statistics?.completed_intro;
};
