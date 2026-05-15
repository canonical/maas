import { useSpaces } from "./spaces";

import { mockSpaces, spacesResolvers } from "@/testing/resolvers/spaces";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(spacesResolvers.listSpaces.handler());

describe("useSpaces", () => {
  it("should return spaces data", async () => {
    const { result } = renderHookWithProviders(useSpaces);
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toMatchObject(mockSpaces);
  });
});
