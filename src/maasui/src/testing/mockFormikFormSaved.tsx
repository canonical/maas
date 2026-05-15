import { vi } from "vitest";
import type { SpyInstance } from "vitest";

import * as baseHooks from "@/app/base/hooks/base";

beforeEach(() => {
  vi.spyOn(baseHooks, "useCycled").mockImplementation(
    (): ReturnType<typeof baseHooks.useCycled> => [false, () => {}]
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

// Simulate FormikForm saved state going from false to true by mocking useCycled
export const mockFormikFormSaved = (): SpyInstance =>
  vi
    .spyOn(baseHooks, "useCycled")
    .mockImplementation(
      (): ReturnType<typeof baseHooks.useCycled> => [true, () => null]
    );
