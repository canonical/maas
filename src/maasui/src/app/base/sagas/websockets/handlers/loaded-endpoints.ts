import type { WebSocketEndpoint } from "@/websocket-client";

let loadedEndpoints: WebSocketEndpoint[] = [];

/**
 * Whether the data is fetching or has been fetched into state.
 *
 * @param endpoint - root redux model and method (e.g. 'users.list')
 * @returns - has data been fetched?
 */
export const isLoaded = (endpoint: WebSocketEndpoint): boolean => {
  return loadedEndpoints.includes(endpoint);
};

/**
 * Mark a model as having been fetched into state.
 *
 * @param endpoint - root redux state model and method (e.g. 'users.list')
 */
export const setLoaded = (endpoint: WebSocketEndpoint): void => {
  if (!isLoaded(endpoint)) {
    loadedEndpoints.push(endpoint);
  }
};

/**
 * Reset the list of loaded endpoints.
 *
 */
export const resetLoaded = (): void => {
  loadedEndpoints = [];
};
