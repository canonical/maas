import { capitaliseFirst } from "./capitaliseFirst";

describe("capitaliseFirst", () => {
  it("correctly capitalises the first letter of a string", () => {
    expect(capitaliseFirst("foo bar")).toEqual("Foo bar");
  });
});
