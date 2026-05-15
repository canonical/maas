import { http, HttpResponse } from "msw";

import { BASE_URL } from "../utils";

import type {
  CreateUserSslkeyError,
  DeleteUserSslkeyError,
  GetUserSslkeysError,
  GetUserSslkeysResponse,
} from "@/app/apiclient";
import { sslKey } from "@/testing/factories";

const mockSslKeys: GetUserSslkeysResponse = {
  items: [
    sslKey({
      id: 1,
      key: "test key",
    }),
    sslKey({
      id: 2,
      key: "test key 2",
    }),
    sslKey({
      id: 3,
      key: "test key 3",
    }),
  ],
  total: 3,
};

const mockGetSslKeysError: GetUserSslkeysError = {
  message: "Unauthorized",
  code: 401,
  kind: "Error", // This will always be 'Error' for every error response
};

const mockCreateSslKeysError: CreateUserSslkeyError = {
  message: "An SSL key with this fingerprint already exists.",
  code: 409,
  kind: "Error",
};

const mockDeleteSslKeyError: DeleteUserSslkeyError = {
  message: "Not found",
  code: 404,
  kind: "Error",
};

const sslKeyResolvers = {
  listSslKeys: {
    resolved: false,
    handler: (data: GetUserSslkeysResponse = mockSslKeys) =>
      http.get(`${BASE_URL}MAAS/a/v3/users/me/sslkeys`, () => {
        sslKeyResolvers.listSslKeys.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: GetUserSslkeysError = mockGetSslKeysError) =>
      http.get(`${BASE_URL}MAAS/a/v3/users/me/sslkeys`, () => {
        sslKeyResolvers.listSslKeys.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  createSslKey: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/users/me/sslkeys`, () => {
        sslKeyResolvers.createSslKey.resolved = true;
        return HttpResponse.json({});
      }),
    error: (error: CreateUserSslkeyError = mockCreateSslKeysError) =>
      http.post(`${BASE_URL}MAAS/a/v3/users/me/sslkeys`, () => {
        sslKeyResolvers.createSslKey.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  deleteSslKey: {
    resolved: false,
    handler: () =>
      http.delete(`${BASE_URL}MAAS/a/v3/users/me/sslkeys/:id`, () => {
        sslKeyResolvers.deleteSslKey.resolved = true;
        return HttpResponse.json({}, { status: 204 });
      }),
    error: (error: DeleteUserSslkeyError = mockDeleteSslKeyError) =>
      http.delete(`${BASE_URL}MAAS/a/v3/users/me/sslkeys/:id`, () => {
        sslKeyResolvers.deleteSslKey.resolved = true;
        return HttpResponse.json(error, { status: 404 });
      }),
  },
};

export { sslKeyResolvers, mockSslKeys };
