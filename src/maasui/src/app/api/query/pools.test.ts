import {
  useCreatePool,
  useDeletePool,
  useGetPool,
  usePoolCount,
  usePools,
  useUpdatePool,
} from "./pools";

import type { ResourcePoolRequest } from "@/app/apiclient";
import { mockPools, poolsResolvers } from "@/testing/resolvers/pools";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

const mockServer = setupMockServer(
  poolsResolvers.listPools.handler(),
  poolsResolvers.getPool.handler(),
  poolsResolvers.createPool.handler(),
  poolsResolvers.updatePool.handler(),
  poolsResolvers.deletePool.handler()
);

describe("usePools", () => {
  it("should return resource pools data", async () => {
    const { result } = renderHookWithProviders(() => usePools());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data?.items).toEqual(mockPools.items);
  });
});

describe("usePoolCount", () => {
  it("should return correct count", async () => {
    const { result } = renderHookWithProviders(() => usePoolCount());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toBe(3);
  });

  it("should return 0 when no pools exist", async () => {
    mockServer.use(poolsResolvers.listPools.handler({ items: [], total: 0 }));
    const { result } = renderHookWithProviders(() => usePoolCount());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toBe(0);
  });
});

describe("useCreatePool", () => {
  it("should create a new pool", async () => {
    const newPool: ResourcePoolRequest = {
      name: "newPool",
      description: "newPoolDescription",
    };
    const { result } = renderHookWithProviders(() => useCreatePool());
    result.current.mutate({ body: newPool });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useGetPool", () => {
  it("should return the correct pool", async () => {
    const expectedPool = mockPools.items[0];
    const { result } = renderHookWithProviders(() =>
      useGetPool({ path: { resource_pool_id: expectedPool.id } })
    );
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(expectedPool);
  });

  it("should return error if pool does not exist", async () => {
    const { result } = renderHookWithProviders(() =>
      useGetPool({ path: { resource_pool_id: 99 } })
    );
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});

describe("useUpdatePool", () => {
  it("should update a pool", async () => {
    const newPool: ResourcePoolRequest = {
      name: "updatedPool",
      description: "updatedPoolDescription",
    };
    const { result } = renderHookWithProviders(() => useUpdatePool());
    result.current.mutate({ body: newPool, path: { resource_pool_id: 1 } });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useDeletePool", () => {
  it("should delete a pool", async () => {
    const { result } = renderHookWithProviders(() => useDeletePool());
    result.current.mutate({ path: { resource_pool_id: 1 } });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});
