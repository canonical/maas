import { preparePayloadParams } from "./preparePayloadParams";

describe("preparePayloadParams", () => {
  it("removes undefined values", () => {
    expect(
      preparePayloadParams({
        id: 0,
        name: undefined,
        emailAddress: null,
      })
    ).toStrictEqual({
      id: 0,
      emailAddress: null,
    });
  });

  it("can map params to different key names", () => {
    expect(
      preparePayloadParams(
        {
          id: 1,
          name: "Wallaby",
        },
        { name: "username" }
      )
    ).toStrictEqual({ id: 1, username: "Wallaby" });
  });
});
