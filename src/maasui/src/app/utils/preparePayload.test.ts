import { preparePayload } from "./preparePayload";

describe("preparePayload", () => {
  it("removes values that are empty strings or are undefined", () => {
    const values = {
      // Should be removed.
      removeUndefined: undefined,
      removeEmptyString: "",
      // Should not be removed,
      dontRemoveZero: 0,
      dontRemoveFalse: false,
    };
    expect(preparePayload(values)).toStrictEqual({
      dontRemoveZero: 0,
      dontRemoveFalse: false,
    });
  });

  it("removes provided entries that should always be removed", () => {
    const values = {
      removeNotEmpty: true,
    };
    expect(preparePayload(values, [], ["removeNotEmpty"])).toStrictEqual({});
  });

  it("does not remove provided entries that are validly empty", () => {
    const values = {
      doNotRemove: "",
    };
    expect(preparePayload(values, ["doNotRemove"])).toStrictEqual({
      doNotRemove: "",
    });
  });
});
