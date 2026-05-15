import {
  loadedEndpoints,
  isLoaded,
  setIsLoaded,
  clearAllLoaded,
} from "./loaded-endpoints";

beforeEach(() => {
  loadedEndpoints.clear();
});

it("returns false for unloaded endpoints", () => {
  expect(isLoaded("test-endpoint")).toBe(false);
});

it("returns true for loaded endpoints", () => {
  setIsLoaded("test-endpoint");
  expect(isLoaded("test-endpoint")).toBe(true);
});

it("clears loaded endpoints", () => {
  setIsLoaded("test-endpoint-1");
  setIsLoaded("test-endpoint-2");
  clearAllLoaded();
  expect(loadedEndpoints.size).toBe(0);
});
