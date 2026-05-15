import { sizeStringToNumber } from "./formatBytes";

describe("sizeStringToNumber", () => {
  it("can convert a size string to a number of bytes", () => {
    expect(sizeStringToNumber("1 B")).toBe(1);
    expect(sizeStringToNumber("1 KB")).toBe(1000);
    expect(sizeStringToNumber("1 GB")).toBe(1000000000);
  });

  it("ignores extra whitespace characters", () => {
    expect(sizeStringToNumber(" 1  B ")).toBe(1);
  });

  it("returns null for an invalid size string parameter", () => {
    expect(sizeStringToNumber("")).toBe(null);
    expect(sizeStringToNumber()).toBe(null);
    expect(sizeStringToNumber("1MB")).toBe(null);
  });
});
