import type { PayloadAction } from "@reduxjs/toolkit";
import { call, put, takeEvery, takeLatest } from "typed-redux-saga";
import type { SagaGenerator } from "typed-redux-saga/macro";

import type { LicenseKeys } from "@/app/store/licensekeys/types";
import type { Script } from "@/app/store/script/types";
import { ScriptResultNames } from "@/app/store/scriptresult/types";
import type { SimpleNode } from "@/app/store/types/node";
import { getCookie } from "@/app/utils";
import { clearCookie, COOKIE_NAMES } from "@/app/utils/cookies";

type CSRFToken = string;

type LoginCredentials = {
  username: string;
  password: string;
};

type UploadScript = {
  type: Script["script_type"];
  contents: string;
  name?: Script["name"];
};

const BAKERY_LOGIN_API = "/MAAS/accounts/discharge-request/";
export const SERVICE_API = "/MAAS/a/v2/";
export const ROOT_API = "/MAAS/api/2.0/";
const SCRIPTS_API = `${ROOT_API}scripts/`;
const LICENSE_KEY_API = `${ROOT_API}license-key/`;
const LICENSE_KEYS_API = `${ROOT_API}license-keys/`;
const LOGIN_API = "/MAAS/a/v3/auth/login";
const LOGOUT_API = "/MAAS/a/v3/auth/logout";
const MACHINES_API = `${ROOT_API}machines/`;
const ZONES_LIST_API = `${SERVICE_API}zones`;

const DEFAULT_HEADERS = {
  "Content-Type": "application/json",
  Accept: "application/json",
};

const handleErrors = (response: Response) => {
  if (!response.ok) {
    throw Error(response.statusText);
  }
  return response;
};

const handlePromise = (response: Response) => {
  const contentType = response.headers.get("Content-Type");
  if (contentType?.includes("application/json")) {
    return Promise.all([response.ok, response.json()]);
  } else {
    return Promise.all([response.ok, response.text()]);
  }
};

const scriptresultsDownload = (
  systemId: SimpleNode["system_id"],
  scriptSetId: string,
  filters?: ScriptResultNames | string,
  filetype?: string
): Promise<Blob | string> => {
  const csrftoken = getCookie("csrftoken");
  // Generate the URL query string.
  const args = new URLSearchParams({
    op: "download",
    ...(filetype ? { filetype } : {}),
    ...(filters ? { filters } : {}),
  }).toString();
  return fetch(`${ROOT_API}nodes/${systemId}/results/${scriptSetId}/?${args}`, {
    method: "GET",
    headers: { ...DEFAULT_HEADERS, "X-CSRFToken": csrftoken || "" },
  })
    .then(handleErrors)
    .then<Blob | string>((response) => {
      if (filetype === "tar.xz") {
        return response.blob();
      }
      return response.text();
    });
};

export const api = {
  auth: {
    checkAuthenticated: (): Promise<{
      is_authenticated: boolean;
      no_users: boolean;
      kind: string;
    }> => {
      const access_token = getCookie(COOKIE_NAMES.LOCAL_JWT_TOKEN_NAME);
      const headers = access_token
        ? { Authorization: `Bearer ${access_token}` }
        : undefined;
      return fetch(LOGIN_API, { headers }).then((response) => {
        const status = response.status.toString();
        if (status.startsWith("5")) {
          // If a 5xx error is returned then the API server is down for
          // some reason.
          throw Error(response.statusText);
        }
        if (status.startsWith("4")) {
          // We take a 4xx error to mean that the user is not authenticated.
          return { authenticated: false };
        }
        return response.json();
      });
    },
    externalLogin: (): Promise<XMLHttpRequest["response"]> => {
      return new Promise(async (resolve, reject) => {
        await import("@/bakery").then(({ default: bakery }) =>
          bakery.get(
            BAKERY_LOGIN_API,
            DEFAULT_HEADERS,
            (_: unknown, response: XMLHttpRequest["response"]) => {
              if (response.currentTarget.status !== 200) {
                localStorage.clear();
                reject(Error(response.currentTarget.responseText));
              } else {
                resolve({ response });
              }
            }
          )
        );
      });
    },
    login: (credentials: LoginCredentials): Promise<void> => {
      const searchParams = new URLSearchParams();
      searchParams.set("username", credentials.username);
      searchParams.set("password", credentials.password);

      return fetch(LOGIN_API, {
        method: "POST",
        mode: "no-cors",
        credentials: "include",
        headers: new Headers({
          Accept: "application/json",
          "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
          "X-Requested-With": "XMLHttpRequest",
        }),
        body: searchParams.toString(),
      })
        .then(handlePromise)
        .then(([responseOk, body]) => {
          if (!responseOk) {
            throw body;
          }
        });
    },
    logout: (csrftoken: CSRFToken): Promise<void> => {
      localStorage.clear();
      return fetch(LOGOUT_API, {
        headers: { "X-CSRFToken": csrftoken },
        method: "POST",
      }).then((res) => {
        handleErrors(res);
        window.location.reload();
      });
    },
  },
  licenseKeys: {
    create: (
      key: LicenseKeys,
      csrftoken: CSRFToken
    ): Promise<Response["body"]> => {
      const { osystem, distro_series, license_key } = key;
      return fetch(`${LICENSE_KEYS_API}`, {
        headers: { ...DEFAULT_HEADERS, "X-CSRFToken": csrftoken },
        method: "POST",
        body: JSON.stringify({ osystem, distro_series, license_key }),
      })
        .then(handlePromise)
        .then(([responseOk, body]) => {
          if (!responseOk) {
            throw body;
          }
          return body;
        });
    },
    update: (
      key: LicenseKeys,
      csrftoken: CSRFToken
    ): Promise<Response["body"]> => {
      const { osystem, distro_series, license_key } = key;
      return fetch(`${LICENSE_KEY_API}${osystem}/${distro_series}`, {
        headers: { ...DEFAULT_HEADERS, "X-CSRFToken": csrftoken },
        method: "PUT",
        body: JSON.stringify({ license_key }),
      })
        .then(handlePromise)
        .then(([responseOk, body]) => {
          if (!responseOk) {
            throw body;
          }
          return body;
        });
    },
    delete: (
      osystem: LicenseKeys["osystem"],
      distro_series: LicenseKeys["distro_series"],
      csrftoken: CSRFToken
    ): Promise<Response> => {
      return fetch(`${LICENSE_KEY_API}${osystem}/${distro_series}`, {
        headers: { ...DEFAULT_HEADERS, "X-CSRFToken": csrftoken },
        method: "DELETE",
      }).then(handleErrors);
    },
    fetch: (csrftoken: CSRFToken): Promise<Response["json"]> => {
      return fetch(`${LICENSE_KEYS_API}`, {
        headers: { ...DEFAULT_HEADERS, "X-CSRFToken": csrftoken },
      })
        .then(handleErrors)
        .then((response) => response.json());
    },
  },
  machines: {
    addChassis: (
      params: Record<string, string>,
      csrftoken: CSRFToken
    ): Promise<Response["body"] | void> => {
      return fetch(`${MACHINES_API}?op=add_chassis`, {
        headers: new Headers({
          "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
          "X-CSRFToken": csrftoken,
          "X-Requested-With": "XMLHttpRequest",
        }),
        method: "POST",
        body: new URLSearchParams(Object.entries(params)),
      })
        .then(handlePromise)
        .then(([responseOk, body]) => {
          if (!responseOk) {
            throw body;
          }
        });
    },
  },
  scriptresults: {
    download: scriptresultsDownload,
    getCurtinLogsTar: (
      systemId: SimpleNode["system_id"]
    ): Promise<Blob | string> =>
      scriptresultsDownload(
        systemId,
        "current-installation",
        ScriptResultNames.CURTIN_LOG
      ),
  },
  scripts: {
    fetch: (csrftoken: CSRFToken): Promise<Response["json"]> => {
      return fetch(`${SCRIPTS_API}?include_script=true`, {
        headers: { ...DEFAULT_HEADERS, "X-CSRFToken": csrftoken },
      })
        .then(handleErrors)
        .then((response) => response.json());
    },
    delete: (
      name: Script["name"],
      csrftoken: CSRFToken
    ): Promise<Response | void> => {
      return fetch(`${SCRIPTS_API}${name}`, {
        headers: { ...DEFAULT_HEADERS, "X-CSRFToken": csrftoken },
        method: "DELETE",
      }).then(handleErrors);
    },
    upload: (
      script: UploadScript,
      csrftoken: CSRFToken
    ): Promise<Response["body"] | void> => {
      const { name, type, contents } = script;
      return fetch(`${SCRIPTS_API}`, {
        headers: { ...DEFAULT_HEADERS, "X-CSRFToken": csrftoken },
        method: "POST",
        body: JSON.stringify({ name, type, script: contents }),
      })
        .then(handlePromise)
        .then(([responseOk, body]) => {
          if (!responseOk) {
            throw body;
          }
        });
    },
  },
  zones: {
    fetch: (csrftoken: CSRFToken): Promise<Response["json"]> => {
      return fetch(`${ZONES_LIST_API}`, {
        headers: { ...DEFAULT_HEADERS, "X-CSRFToken": csrftoken },
      })
        .then(handleErrors)
        .then((response) => response.json());
    },
  },
};

export function* checkAuthenticatedSaga(): SagaGenerator<void> {
  try {
    yield* put({ type: "status/checkAuthenticatedStart" });
    const response = yield* call(api.auth.checkAuthenticated);
    if (!response.is_authenticated) {
      clearCookie(COOKIE_NAMES.LOCAL_JWT_TOKEN_NAME, { path: "/" });
      clearCookie(COOKIE_NAMES.LOCAL_REFRESH_TOKEN_NAME, { path: "/" });
    }
    yield* put({
      payload: response,
      type: "status/checkAuthenticatedSuccess",
    });
  } catch (error) {
    yield* put({
      error: true,
      payload: error instanceof Error ? error.message : error,
      type: "status/checkAuthenticatedError",
    });
  }
}

export function* loginSaga(
  action: PayloadAction<LoginCredentials>
): SagaGenerator<void> {
  try {
    yield* put({ type: "status/loginStart" });
    yield* call(api.auth.login, action.payload);
    yield* put({
      type: "status/loginSuccess",
    });
    yield* put({
      type: "status/websocketConnect",
    });
  } catch (error) {
    yield* put({
      error: true,
      payload: error,
      type: "status/loginError",
    });
  }
}

export function* logoutSaga(): SagaGenerator<void> {
  const csrftoken = yield* call(getCookie, "csrftoken");
  if (!csrftoken) {
    return;
  }
  try {
    yield* put({ type: "status/logoutStart" });
    yield* call(api.auth.logout, csrftoken);
    yield* put({
      type: "status/logoutSuccess",
    });
    yield* put({
      type: "status/websocketDisconnect",
    });
  } catch (error) {
    yield* put({
      error: true,
      payload: { error: error instanceof Error ? error.message : error },
      type: "status/logoutError",
    });
  }
}

export function* externalLoginSaga(): SagaGenerator<void> {
  try {
    yield* put({ type: "status/externalLoginStart" });
    yield* call(api.auth.externalLogin);
    yield* put({
      type: "status/externalLoginSuccess",
    });
    yield* put({
      type: "status/websocketConnect",
    });
  } catch (error) {
    yield* put({
      error: true,
      payload: error instanceof Error ? error.message : error,
      type: "status/externalLoginError",
    });
  }
}

export function* fetchLicenseKeysSaga(): SagaGenerator<void> {
  const csrftoken = yield* call(getCookie, "csrftoken");
  if (!csrftoken) {
    return;
  }
  let response;
  try {
    yield* put({ type: "licensekeys/fetchStart" });
    response = yield* call(api.licenseKeys.fetch, csrftoken);
    yield* put({
      type: "licensekeys/fetchSuccess",
      payload: response,
    });
  } catch (error) {
    yield* put({
      errors: true,
      payload: { error: error instanceof Error ? error.message : error },
      type: "licensekeys/fetchError",
    });
  }
}

export function* deleteLicenseKeySaga(
  action: PayloadAction<{
    osystem: LicenseKeys["osystem"];
    distro_series: LicenseKeys["distro_series"];
  }>
): SagaGenerator<void> {
  const csrftoken = yield* call(getCookie, "csrftoken");
  if (!csrftoken) {
    return;
  }
  try {
    yield* put({ type: "licensekeys/deleteStart" });
    yield* call(
      api.licenseKeys.delete,
      action.payload.osystem,
      action.payload.distro_series,
      csrftoken
    );
    yield* put({
      type: "licensekeys/deleteSuccess",
      payload: action.payload,
    });
  } catch (error) {
    yield* put({
      errors: true,
      payload: { error: error instanceof Error ? error.message : error },
      type: "licensekeys/deleteError",
    });
  }
}

export function* createLicenseKeySaga(
  action: PayloadAction<LicenseKeys>
): SagaGenerator<void> {
  const csrftoken = yield* call(getCookie, "csrftoken");
  if (!csrftoken) {
    return;
  }
  const key = action.payload;
  let response;
  try {
    yield* put({ type: "licensekeys/createStart" });
    response = yield* call(api.licenseKeys.create, key, csrftoken);
    yield* put({
      type: "licensekeys/createSuccess",
      payload: response,
    });
  } catch (errors) {
    let error = errors;
    if (typeof error === "string") {
      error = { "Create error": error };
    }
    yield* put({
      errors: true,
      payload: error,
      type: "licensekeys/createError",
    });
  }
}

export function* updateLicenseKeySaga(
  action: PayloadAction<LicenseKeys>
): SagaGenerator<void> {
  const csrftoken = yield* call(getCookie, "csrftoken");
  if (!csrftoken) {
    return;
  }
  const key = action.payload;
  let response;
  try {
    yield* put({ type: "licensekeys/updateStart" });
    response = yield* call(api.licenseKeys.update, key, csrftoken);
    yield* put({
      type: "licensekeys/updateSuccess",
      payload: response,
    });
  } catch (errors) {
    let error = errors;
    if (typeof error === "string") {
      error = { "Create error": error };
    }
    yield* put({
      errors: true,
      payload: error,
      type: "licensekeys/updateError",
    });
  }
}

export function* uploadScriptSaga(
  action: PayloadAction<UploadScript>
): SagaGenerator<void> {
  const csrftoken = yield* call(getCookie, "csrftoken");
  if (!csrftoken) {
    return;
  }
  const script = action.payload;
  let response;
  try {
    yield* put({ type: "script/uploadStart" });
    response = yield* call(api.scripts.upload, script, csrftoken);
    yield* put({
      type: "script/uploadSuccess",
      payload: response,
    });
  } catch (errors) {
    let error = errors;
    if (typeof error === "string") {
      error = { "Upload error": error };
    }
    yield* put({
      errors: true,
      payload: error,
      type: "script/uploadError",
    });
  }
}

export function* addMachineChassisSaga(
  action: PayloadAction<{ params: Record<string, string> }>
): SagaGenerator<void> {
  const csrftoken = yield* call(getCookie, "csrftoken");
  if (!csrftoken) {
    return;
  }
  const params = action.payload.params;
  let response;
  try {
    yield* put({ type: "machine/addChassisStart" });
    response = yield* call(api.machines.addChassis, params, csrftoken);
    yield* put({
      type: "machine/addChassisSuccess",
      payload: response,
    });
  } catch (err) {
    yield* put({
      type: "machine/addChassisError",
      payload: err,
    });
  }
}

export function* watchExternalLogin(): SagaGenerator<void> {
  yield* takeLatest("status/externalLogin", externalLoginSaga);
}

export function* watchLogin(): SagaGenerator<void> {
  yield* takeLatest("status/login", loginSaga);
}

export function* watchLogout(): SagaGenerator<void> {
  yield* takeLatest("status/logout", logoutSaga);
}

export function* watchCheckAuthenticated(): SagaGenerator<void> {
  yield* takeLatest("status/checkAuthenticated", checkAuthenticatedSaga);
}

export function* watchCreateLicenseKey(): SagaGenerator<void> {
  yield* takeLatest("licensekeys/create", createLicenseKeySaga);
}

export function* watchUpdateLicenseKey(): SagaGenerator<void> {
  yield* takeLatest("licensekeys/update", updateLicenseKeySaga);
}

export function* watchDeleteLicenseKey(): SagaGenerator<void> {
  yield* takeEvery("licensekeys/delete", deleteLicenseKeySaga);
}

export function* watchFetchLicenseKeys(): SagaGenerator<void> {
  yield* takeLatest("licensekeys/fetch", fetchLicenseKeysSaga);
}

export function* watchUploadScript(): SagaGenerator<void> {
  yield* takeEvery("script/upload", uploadScriptSaga);
}

export function* watchAddMachineChassis(): SagaGenerator<void> {
  yield* takeEvery("machine/addChassis", addMachineChassisSaga);
}
