import { COOKIE_NAMES } from "../utils/cookies";

import { client } from "@/app/apiclient/client.gen";
import { getCookie } from "@/app/utils";

/**
 * Configures the API client to automatically include Authorization header
 * with Bearer token on all requests.
 */
export const configureAuthInterceptor = () => {
  client.interceptors.request.use((request) => {
    const token = getCookie(COOKIE_NAMES.LOCAL_JWT_TOKEN_NAME);

    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }

    return request;
  });
};
