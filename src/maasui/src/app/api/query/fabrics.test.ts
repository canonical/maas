import { useFabrics } from "./fabrics";

import { fabricsResolvers, mockFabrics } from "@/testing/resolvers/fabrics";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(fabricsResolvers.listFabrics.handler());

describe("useFabrics", () => {
  it("should return fabrics data", async () => {
    const { result } = renderHookWithProviders(useFabrics);
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toMatchObject(mockFabrics);
  });
});
