import { someInArray } from "./someInArray";

describe("someInArray", () => {
  it("correctly returns whether a subset of given items is in an array", () => {
    expect(someInArray([1], [1, 2])).toBe(true);
    expect(someInArray([1, 2], [1, 2])).toBe(true);
    expect(someInArray([2, 3], [1, 2])).toBe(true);
    expect(someInArray(1, [1, 2])).toBe(true);
    expect(someInArray(3, [1, 2])).toBe(false);
    expect(someInArray(undefined, [1, 2])).toBe(false);
  });
});
