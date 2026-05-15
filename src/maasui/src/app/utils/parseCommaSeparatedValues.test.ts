import { parseCommaSeparatedValues } from "./parseCommaSeparatedValues";

describe("parseCommaSeparatedValues", () => {
  it("should correctly parse a single value with no spaces", () => {
    expect(parseCommaSeparatedValues("value")).toEqual(["value"]);
  });

  it("should correctly parse multiple values with spaces", () => {
    expect(parseCommaSeparatedValues("apple, banana, cherry")).toEqual([
      "apple",
      "banana",
      "cherry",
    ]);
  });

  it("should handle leading and trailing spaces", () => {
    expect(parseCommaSeparatedValues("  apple, banana ,  cherry ")).toEqual([
      "apple",
      "banana",
      "cherry",
    ]);
  });

  it("should ignore empty strings between commas", () => {
    expect(parseCommaSeparatedValues("apple,,banana, ,cherry")).toEqual([
      "apple",
      "banana",
      "cherry",
    ]);
  });

  it("should return an empty array if the input is only commas or spaces", () => {
    expect(parseCommaSeparatedValues(" , , , ")).toEqual([]);
  });

  it("should return an empty array if the input is an empty string", () => {
    expect(parseCommaSeparatedValues("")).toEqual([]);
  });
});
