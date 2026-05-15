import messages from "./selectors";

import * as factory from "@/testing/factories";

describe("messages", () => {
  it("can get all messages", () => {
    const state = factory.rootState({
      message: factory.messageState({
        items: [
          factory.message({
            message: "User added",
          }),
        ],
      }),
    });
    const items = messages.all(state);
    expect(items.length).toEqual(1);
    expect(items[0].message).toEqual("User added");
  });

  it("can get the count of messages", () => {
    const state = factory.rootState({
      message: factory.messageState({
        items: [
          factory.message({
            message: "User added",
          }),
        ],
      }),
    });
    const count = messages.count(state);
    expect(count).toEqual(1);
  });
});
