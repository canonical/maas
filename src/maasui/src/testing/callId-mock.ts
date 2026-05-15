import * as reduxToolkit from "@reduxjs/toolkit";

import * as query from "@/app/store/machine/utils/query";

export const callId = "mocked-nanoid";

export const enableCallIdMocks = (id = callId): void => {
  vi.mock("@reduxjs/toolkit", async () => {
    const actual: object = await vi.importActual("@reduxjs/toolkit");
    return {
      ...actual,
      nanoid: vi.fn(),
    };
  });

  beforeEach(() => {
    vi.spyOn(query, "generateCallId").mockReturnValue(id);
    vi.spyOn(reduxToolkit, "nanoid").mockReturnValue(id);
  });

  afterEach(() => {
    vi.spyOn(query, "generateCallId").mockRestore();
    vi.spyOn(reduxToolkit, "nanoid").mockRestore();
  });
};
