import reducers from "./slice";

import * as factory from "@/testing/factories";

describe("reducers", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toStrictEqual(
      factory.messageState({
        items: [],
      })
    );
  });

  it("should correctly reduce message/add", () => {
    const message = factory.message({
      message: "User added",
    });
    expect(
      reducers(undefined, {
        type: "message/add",
        payload: message,
      })
    ).toStrictEqual(
      factory.messageState({
        items: [message],
      })
    );
  });

  it("should correctly reduce message/remove", () => {
    expect(
      reducers(
        factory.messageState({
          items: [
            factory.message({
              id: 99,
              message: "User added",
            }),
            factory.message({
              id: 100,
              message: "User updated",
            }),
          ],
        }),
        {
          type: "message/remove",
          payload: 99,
        }
      )
    ).toStrictEqual(
      factory.messageState({
        items: [
          factory.message({
            id: 100,
            message: "User updated",
          }),
        ],
      })
    );
  });
});
