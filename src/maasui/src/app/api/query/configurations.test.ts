import {
  useBulkSetConfigurations,
  useConfigurations,
  useGetConfiguration,
  useSetConfiguration,
} from "./configurations";

import {
  configurationsResolvers,
  mockConfigurations,
} from "@/testing/resolvers/configurations";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  configurationsResolvers.getConfiguration.handler(),
  configurationsResolvers.listConfigurations.handler(),
  configurationsResolvers.setConfiguration.handler(),
  configurationsResolvers.setBulkConfigurations.handler()
);

describe("useConfigurations", () => {
  it("should return configurations data", async () => {
    const { result } = renderHookWithProviders(() => useConfigurations());

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toMatchObject(mockConfigurations);
  });
});

describe("useGetConfiguration", () => {
  it("should return a single configuration", async () => {
    const { result } = renderHookWithProviders(() =>
      useGetConfiguration({ path: { name: "maas_name" } })
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toMatchObject(mockConfigurations.items[0]);
  });
});

describe("useSetConfiguration", () => {
  it("should set a configuration", async () => {
    const { result } = renderHookWithProviders(() => useSetConfiguration());
    result.current.mutate({
      path: { name: "maas_name" },
      body: { value: "test maas" },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useBulkSetConfiguration", () => {
  it("should set many configurations", async () => {
    const { result } = renderHookWithProviders(() =>
      useBulkSetConfigurations()
    );

    result.current.mutate({
      body: {
        configurations: [
          { name: "maas_name", value: "test maas" },
          { name: "active_discovery_interval", value: 30000 },
        ],
      },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});
