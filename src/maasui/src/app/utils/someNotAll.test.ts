import { someNotAll } from "./someNotAll";

describe("someNotAll", () => {
  it("returns whether some, but not all, items in an array are in another array", () => {
    expect(someNotAll([1, 3], [1, 2])).toBe(true);
    expect(someNotAll([1], [1, 2])).toBe(false);
    expect(someNotAll([1, 2], [1, 2])).toBe(false);
  });
});
