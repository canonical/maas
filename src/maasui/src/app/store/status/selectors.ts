import type { APIError } from "@/app/base/types";
import type { RootState } from "@/app/store/root/types";

/**
 * Whether the user is authenticated.
 * @param {RootState} state - The redux state.
 * @returns {StatusState["authenticated"]} TheStatusState authentication status.
 */
const authenticated = (state: RootState): boolean => state.status.authenticated;

/**
 * Whether the user is authenticating.
 * @param {RootState} state - The redux state.
 * @returns {StatusState["authenticating"]} The user authentication status.
 */
const authenticating = (state: RootState): boolean =>
  state.status.authenticating;

/**
 * Whether the websocket is connected.
 * @param {RootState} state - The redux state.
 * @returns {StatusState["connected"]}StatusState websocket connected status.
 */
const connected = (state: RootState): boolean => state.status.connected;

/**
 * Whether the websocket is connecting.
 * @param {RootState} state - The redux state.
 * @returns {StatusState["connecting"]} TheStatusState connecting status.
 */
const connecting = (state: RootState): boolean => state.status.connecting;

/**
 * Number of times the websocket has been connected.
 * @param {RootState} state - The redux state.
 * @returns {StatusState["connecting"]} TheStatusState connecting status.
 */
const connectedCount = (state: RootState): number =>
  state.status.connectedCount;

/**
 * Status errors.
 * @param {RootState} state - The redux state.
 * @returns {StatusState["error"]} TheStatusState error status.
 */
const error = (state: RootState): APIError => state.status.error;

/**
 * An authentication error.
 * @param {RootState} state - The redux state.
 * @returns {StatusState["authenticationError"]} The authentication error status.
 */
const authenticationError = (state: RootState): APIError =>
  state.status.authenticationError;

/**
 * Get the external auth url.
 * @param {RootState} state - The redux state.
 * @returns {StatusState["externalAuthURL"]} The external auth url.
 */
const externalAuthURL = (state: RootState): string | null =>
  state.status.externalAuthURL;

/**
 * Get the external login url.
 * @param {RootState} state - The redux state.
 * @returns {StatusState["externalLoginURL"]} The external login url.
 */
const externalLoginURL = (state: RootState): string | null =>
  state.status.externalLoginURL;

/**
 * Whether there are currently no MAAS users.
 * @param {RootState} state - The redux state.
 * @returns {StatusState["noUsers"]}StatusState users in MAAS.
 */
const noUsers = (state: RootState): boolean => state.status.noUsers;

const status = {
  authenticated,
  authenticating,
  authenticationError,
  connected,
  connecting,
  connectedCount,
  error,
  externalAuthURL,
  externalLoginURL,
  noUsers,
};

export default status;
