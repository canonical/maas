import { unindentString } from "./unindentString";

describe("unindentString", () => {
  it("removes excess spaces", () => {
    expect(unindentString(" so  much    space   ")).toBe("so much space");
  });

  it("removes newlines", () => {
    expect(unindentString("first line\nsecond line")).toBe(
      "first line second line"
    );
    expect(
      unindentString(
        `first line
        second line`
      )
    ).toBe("first line second line");
    expect(
      unindentString(`
        first line
        second line
      `)
    ).toBe("first line second line");
  });

  it("handles an empty string", () => {
    expect(unindentString("")).toBe("");
  });
});
