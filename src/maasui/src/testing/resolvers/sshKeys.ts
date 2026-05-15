import { http, HttpResponse } from "msw";

import { BASE_URL } from "../utils";

import type {
  CreateUserSshkeysError,
  DeleteUserSshkeyError,
  ImportUserSshkeysError,
  ListUserSshkeysError,
  ListUserSshkeysResponse,
} from "@/app/apiclient";
import { sshKey as sshKeyFactory } from "@/testing/factories";

const mockSshKeys: ListUserSshkeysResponse = {
  items: [
    sshKeyFactory({
      id: 1,
      protocol: "lp",
      auth_id: "test auth id",
      kind: "sshkey",
      key: "test key",
    }),
    sshKeyFactory({
      id: 2,
      protocol: undefined,
      auth_id: undefined,
      kind: "sshkey",
      key: "test key 2",
    }),
    sshKeyFactory({
      id: 3,
      protocol: "gh",
      auth_id: "another test auth id",
      kind: "sshkey",
      key: "test key 3",
    }),
  ],
  total: 3,
};

const mockListSshKeysError: ListUserSshkeysError = {
  message: "Unauthorized",
  code: 401,
  kind: "Error", // This will always be 'Error' for every error response
};

const mockCreateSshKeysError: CreateUserSshkeysError = {
  message: "An SSH key with this fingerprint already exists.",
  code: 409,
  kind: "Error",
};

const mockImportSshKeysError: ImportUserSshkeysError = {
  message: "Internal server error",
  code: 500,
  kind: "Error",
};

const mockDeleteSshKeyError: DeleteUserSshkeyError = {
  message: "Not found",
  code: 404,
  kind: "Error",
};

const sshKeyResolvers = {
  listSshKeys: {
    resolved: false,
    handler: (data: ListUserSshkeysResponse = mockSshKeys) =>
      http.get(`${BASE_URL}MAAS/a/v3/users/me/sshkeys`, () => {
        sshKeyResolvers.listSshKeys.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListUserSshkeysError = mockListSshKeysError) =>
      http.get(`${BASE_URL}MAAS/a/v3/users/me/sshkeys`, () => {
        sshKeyResolvers.listSshKeys.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  createSshKey: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/users/me/sshkeys`, () => {
        sshKeyResolvers.createSshKey.resolved = true;
        return HttpResponse.json({});
      }),
    error: (error: CreateUserSshkeysError = mockCreateSshKeysError) =>
      http.post(`${BASE_URL}MAAS/a/v3/users/me/sshkeys`, () => {
        sshKeyResolvers.createSshKey.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  importSshKey: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/users/me/sshkeys:import`, () => {
        sshKeyResolvers.importSshKey.resolved = true;
        return HttpResponse.json({});
      }),
    error: (error: ImportUserSshkeysError = mockImportSshKeysError) =>
      http.post(`${BASE_URL}MAAS/a/v3/users/me/sshkeys:import`, () => {
        sshKeyResolvers.importSshKey.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  deleteSshKey: {
    resolved: false,
    handler: () =>
      http.delete(`${BASE_URL}MAAS/a/v3/users/me/sshkeys/:id`, () => {
        sshKeyResolvers.deleteSshKey.resolved = true;
        return HttpResponse.json({}, { status: 204 });
      }),
    error: (error: DeleteUserSshkeyError = mockDeleteSshKeyError) =>
      http.delete(`${BASE_URL}MAAS/a/v3/users/me/sshkeys/:id`, () => {
        sshKeyResolvers.deleteSshKey.resolved = true;
        return HttpResponse.json(error, { status: 404 });
      }),
  },
};

export { sshKeyResolvers, mockSshKeys };
