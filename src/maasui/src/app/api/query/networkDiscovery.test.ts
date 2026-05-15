import {
  useClearNetworkDiscoveries,
  useNetworkDiscoveries,
} from "@/app/api/query/networkDiscovery";
import {
  mockNetworkDiscoveries,
  networkDiscoveryResolvers,
} from "@/testing/resolvers/networkDiscovery";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  networkDiscoveryResolvers.listNetworkDiscoveries.handler(),
  networkDiscoveryResolvers.clearNetworkDiscoveries.handler()
);

describe("useNetworkDiscoveries", () => {
  it("should return network discovery data", async () => {
    const { result } = renderHookWithProviders(() => useNetworkDiscoveries());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(mockNetworkDiscoveries);
  });
});

describe("useClearNetworkDiscoveries", () => {
  it("should clear network discoveries", async () => {
    const { result } = renderHookWithProviders(() =>
      useClearNetworkDiscoveries()
    );
    result.current.mutate({});
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});
