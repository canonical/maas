type CookieOptions = {
  path?: string;
  domain?: string;
  expires?: Date;
  maxAge?: number;
  secure?: boolean;
  sameSite?: "Lax" | "None" | "Strict";
};

const LOCAL_JWT_TOKEN_NAME = "maas.local_jwt_token_cookie";
const LOCAL_REFRESH_TOKEN_NAME = "maas.local_refresh_token_cookie";

export const COOKIE_NAMES = {
  LOCAL_JWT_TOKEN_NAME,
  LOCAL_REFRESH_TOKEN_NAME,
};

/**
 * Get cookie value by name.
 *
 * @param {string} n - cookie name.
 * @returns {string} - cookie value.
 */
export const getCookie = (n: string): string | null => {
  const cookie = `; ${document.cookie}`.match(`;\\s*${n}=([^;]+)`);
  return cookie ? cookie[1] : null;
};

/**
 * Sets a cookie in the browser with the specified key, value, and options.
 *
 * @param {string} key - cookie name.
 * @param {string} value - cookie value.
 * @param {Object} [options] - additional cookie options.
 */
export const setCookie = (
  key: string,
  value: string,
  options: CookieOptions = {}
): void => {
  let cookie = `${encodeURIComponent(key)}=${encodeURIComponent(value)}`;
  if (options.expires) {
    cookie += `; Expires=${options.expires.toUTCString()}`;
  }

  if (options.maxAge !== undefined) {
    cookie += `; Max-Age=${options.maxAge}`;
  }

  if (options.path) {
    cookie += `; Path=${options.path}`;
  }

  if (options.domain) {
    cookie += `; Domain=${options.domain}`;
  }

  if (options.sameSite) {
    cookie += `; SameSite=${options.sameSite}`;
  }

  if (options.secure) {
    cookie += `; Secure`;
  }
  document.cookie = cookie;
};

/** Clears a cookie by setting its expiration date to a past date.
 *
 * @param {string} name - cookie name.
 * @param {Object} [options] - additional cookie options.
 */
export const clearCookie = (
  name: string,
  options: CookieOptions = {}
): void => {
  setCookie(name, "", {
    ...options,
    expires: new Date(0),
    maxAge: 0,
  });
};
