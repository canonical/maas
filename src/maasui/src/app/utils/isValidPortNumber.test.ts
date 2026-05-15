import { isValidPortNumber } from ".";

it("returns true for any number between 0 and 65535", () => {
  expect(isValidPortNumber(0)).toBe(true);
  expect(isValidPortNumber(80)).toBe(true);
  expect(isValidPortNumber(443)).toBe(true);
  expect(isValidPortNumber(1234)).toBe(true);
  expect(isValidPortNumber(5240)).toBe(true);
  expect(isValidPortNumber(8400)).toBe(true);
  expect(isValidPortNumber(65535)).toBe(true);
});

it("returns false for numbers larger than 65535", () => {
  expect(isValidPortNumber(65536)).toBe(false);
});

it("returns false for numbers smaller than 0", () => {
  expect(isValidPortNumber(-1)).toBe(false);
});
