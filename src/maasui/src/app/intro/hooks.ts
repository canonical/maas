import urls from "@/app/base/urls";

/**
 * Get the URL to redirect to when the intro closes.
 * @returns The URL to redirect to.
 */
export const useExitURL = (): string => {
  return urls.machines.index;
};
