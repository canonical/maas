import {
  useCreateSshKeys,
  useDeleteSshKey,
  useImportSshKeys,
  useListSshKeys,
} from "./sshKeys";

import type {
  SshKeyImportFromSourceRequest,
  SshKeyManualUploadRequest,
} from "@/app/apiclient";
import { mockSshKeys, sshKeyResolvers } from "@/testing/resolvers/sshKeys";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  sshKeyResolvers.listSshKeys.handler(),
  sshKeyResolvers.createSshKey.handler(),
  sshKeyResolvers.importSshKey.handler(),
  sshKeyResolvers.deleteSshKey.handler()
);

describe("useListSshKeys", () => {
  it("should return SSH keys data", async () => {
    const { result } = renderHookWithProviders(() => useListSshKeys());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data?.items).toEqual(mockSshKeys.items);
  });
});

describe("useCreateSshKeys", () => {
  it("should create a new SSH key", async () => {
    const newSshKey: SshKeyManualUploadRequest = {
      key: "ssh-rsa aabb",
    };
    const { result } = renderHookWithProviders(() => useCreateSshKeys());
    result.current.mutate({ body: newSshKey });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useImportSshKeys", () => {
  it("should import a new SSH key", async () => {
    const newSshKey: SshKeyImportFromSourceRequest = {
      protocol: "lp",
      auth_id: "coolUsername",
    };
    const { result } = renderHookWithProviders(() => useImportSshKeys());
    result.current.mutate({ body: newSshKey });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useDeleteSshKey", () => {
  it("should delete an SSH key", async () => {
    const { result } = renderHookWithProviders(() => useDeleteSshKey());
    result.current.mutate({ path: { id: 1 } });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});
