import { actions } from "./slice";

describe("base actions", () => {
  it("should handle adding a message and increment ids", () => {
    expect(actions.add("User added", "negative", "Error", true)).toEqual({
      type: "message/add",
      payload: {
        id: 1,
        message: "User added",
        severity: "negative",
        temporary: true,
        title: "Error",
      },
    });

    expect(actions.add("User added", "negative", "Error", true)).toEqual({
      type: "message/add",
      payload: {
        id: 2,
        message: "User added",
        severity: "negative",
        temporary: true,
        title: "Error",
      },
    });
  });

  it("should handle removing a message", () => {
    expect(actions.remove(1)).toEqual({
      type: "message/remove",
      payload: 1,
    });
  });
});
