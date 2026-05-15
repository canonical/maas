import {
  useZones,
  useZoneCount,
  useGetZone,
  useCreateZone,
  useUpdateZone,
  useDeleteZone,
  useZonesStatistics,
} from "@/app/api/query/zones";
import type { ZoneRequest } from "@/app/apiclient";
import {
  mockZones,
  zoneResolvers,
  mockZonesWithStatistics,
} from "@/testing/resolvers/zones";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

const mockServer = setupMockServer(
  zoneResolvers.listZones.handler(),
  zoneResolvers.listZonesWithStatistics.handler(),
  zoneResolvers.getZone.handler(),
  zoneResolvers.createZone.handler(),
  zoneResolvers.updateZone.handler(),
  zoneResolvers.deleteZone.handler()
);

describe("useZones", () => {
  it("should return zones data", async () => {
    const { result } = renderHookWithProviders(() => useZones());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(mockZones);
  });
});

describe("useZonesStatistics", () => {
  it("should return zones statistics data", async () => {
    const { result } = renderHookWithProviders(() => useZonesStatistics());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data?.items[0]).toMatchObject(
      mockZonesWithStatistics.items[0]
    );
  });
});

describe("useZoneCount", () => {
  it("should return correct count", async () => {
    const { result } = renderHookWithProviders(() => useZoneCount());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toBe(3);
  });

  it("should return 0 when no zones exist", async () => {
    mockServer.use(zoneResolvers.listZones.handler({ items: [], total: 0 }));
    const { result } = renderHookWithProviders(() => useZoneCount());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toBe(0);
  });
});

describe("useGetZone", () => {
  it("should return the correct zone", async () => {
    const expectedZone = mockZones.items[0];
    const { result } = renderHookWithProviders(() =>
      useGetZone({ path: { zone_id: expectedZone.id } })
    );
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(expectedZone);
  });

  it("should return error if zone does not exist", async () => {
    const { result } = renderHookWithProviders(() =>
      useGetZone({ path: { zone_id: 99 } })
    );
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});

describe("useCreateZone", () => {
  it("should create a new zone", async () => {
    const newZone: ZoneRequest = {
      name: "new-zone",
      description: "This is a new zone.",
    };
    const { result } = renderHookWithProviders(() => useCreateZone());
    result.current.mutate({ body: newZone });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    const { result: listResult } = renderHookWithProviders(() => useZones());
    await waitFor(() => {
      expect(listResult.current.isSuccess).toBe(true);
    });
  });
});

describe("useUpdateZone", () => {
  it("should update an existing zone", async () => {
    const updatedZone = { ...mockZones.items[0], description: "Edited" };
    const { result } = renderHookWithProviders(() => useUpdateZone());
    result.current.mutate({
      body: updatedZone,
      path: { zone_id: updatedZone.id },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    const { result: listResult } = renderHookWithProviders(() => useZones());
    await waitFor(() => {
      expect(listResult.current.isSuccess).toBe(true);
    });
  });
});

describe("useDeleteZone", () => {
  it("should delete a zone", async () => {
    const zoneToDelete = mockZones.items[0];
    const { result } = renderHookWithProviders(() => useDeleteZone());
    result.current.mutate({ path: { zone_id: zoneToDelete.id } });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    const { result: listResult } = renderHookWithProviders(() => useZones());
    await waitFor(() => {
      expect(listResult.current.isSuccess).toBe(true);
    });
  });
});
