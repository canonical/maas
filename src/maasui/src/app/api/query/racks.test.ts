import {
  useCreateRack,
  useDeleteRack,
  useGenerateToken,
  useGetRack,
  useRacks,
  useUpdateRack,
} from "./racks";

import type { RackRequest } from "@/app/apiclient";
import { mockRacks, rackResolvers } from "@/testing/resolvers/racks";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  rackResolvers.listRacks.handler(),
  rackResolvers.createRack.handler(),
  rackResolvers.getRack.handler(),
  rackResolvers.updateRack.handler(),
  rackResolvers.deleteRack.handler(),
  rackResolvers.generateToken.handler()
);

describe("useRacks", () => {
  it("should return racks data", async () => {
    const { result } = renderHookWithProviders(() => useRacks());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data?.items).toEqual(mockRacks.items);
  });
});

describe("useGetRack", () => {
  it("should return the correct rack", async () => {
    const expectedRack = mockRacks.items[0];
    const { result } = renderHookWithProviders(() =>
      useGetRack({ path: { rack_id: expectedRack.id } })
    );
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(expectedRack);
  });

  it("should return error if rack does not exist", async () => {
    const { result } = renderHookWithProviders(() =>
      useGetRack({ path: { rack_id: 99 } })
    );
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});

describe("useCreateRack", () => {
  it("should create a new rack", async () => {
    const newRack: RackRequest = {
      name: "newRack",
    };
    const { result } = renderHookWithProviders(() => useCreateRack());
    result.current.mutate({ body: newRack });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useUpdateRack", () => {
  it("should update a rack", async () => {
    const newRack: RackRequest = {
      name: "updatedRack",
    };
    const { result } = renderHookWithProviders(() => useUpdateRack());
    result.current.mutate({ body: newRack, path: { rack_id: 1 } });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useDeleteRack", () => {
  it("should delete a rack", async () => {
    const { result } = renderHookWithProviders(() => useDeleteRack());
    result.current.mutate({ path: { rack_id: 1 } });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useGenerateToken", () => {
  it("should generate a bootstrap token", async () => {
    const { result } = renderHookWithProviders(() => useGenerateToken());
    result.current.mutate({ path: { rack_id: 1 } });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});
