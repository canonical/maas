import { useCreateSslKeys, useDeleteSslKey, useGetSslKeys } from "./sslKeys";

import type { SslKeyRequest } from "@/app/apiclient";
import { mockSslKeys, sslKeyResolvers } from "@/testing/resolvers/sslKeys";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  sslKeyResolvers.listSslKeys.handler(),
  sslKeyResolvers.createSslKey.handler(),
  sslKeyResolvers.deleteSslKey.handler()
);

describe("useGetSslKeys", () => {
  it("should return SSL keys data", async () => {
    const { result } = renderHookWithProviders(() => useGetSslKeys());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(mockSslKeys);
  });
});

describe("useCreateSslKeys", () => {
  it("should create a new SSL key", async () => {
    const newSslKey: SslKeyRequest = {
      key: "ssl-rsa aabb",
    };
    const { result } = renderHookWithProviders(() => useCreateSslKeys());
    result.current.mutate({ body: newSslKey });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useDeleteSslKey", () => {
  it("should delete an SSL key", async () => {
    const { result } = renderHookWithProviders(() => useDeleteSslKey());
    result.current.mutate({ path: { sslkey_id: 1 } });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});
