type Endpoint = string;
type EndpointState = { fetchedAt: number };

export const loadedEndpoints = new Map<Endpoint, EndpointState>();

/**
 * Whether an endpoint associated with an action type has already been fetched.
 */
export const isLoaded = (endpoint: Endpoint): boolean => {
  return loadedEndpoints.has(endpoint);
};

/**
 * Mark an endpoint associated with an action type as having been fetched.
 */
export const setIsLoaded = (endpoint: Endpoint): void => {
  loadedEndpoints.set(endpoint, { fetchedAt: Date.now() });
};

/**
 * Clear the loaded state of all endpoints.
 */
export const clearAllLoaded = (): void => {
  loadedEndpoints.clear();
};
