import { formatMacAddress } from "./formatMacAddress";

describe("formatMacAddress", () => {
  it("returns the value unchanged if MAC address is formatted correctly", () => {
    expect(formatMacAddress("")).toEqual("");
    expect(formatMacAddress("12:3")).toEqual("12:3");
    expect(formatMacAddress("12:34:56:78:9a:bc")).toEqual("12:34:56:78:9a:bc");
  });

  it("can correctly splice in separators", () => {
    expect(formatMacAddress("123")).toEqual("12:3");
    expect(formatMacAddress("123456789abc")).toEqual("12:34:56:78:9a:bc");
  });

  it("stops adding separators after the fifth one", () => {
    expect(formatMacAddress("123456789abcde")).toEqual("12:34:56:78:9a:bcde");
  });
});
