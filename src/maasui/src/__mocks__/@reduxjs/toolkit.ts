import { vi } from "vitest";

const toolkit = vi.importActual("@reduxjs/toolkit");

let id = 0;

module.exports = {
  ...toolkit,
  nanoid: () => {
    id++;
    // The generated ids need to be unique, but deterministic. This is so that
    // snapshots include the same ids each time the test is run, but also
    // provides unique ids for each element so that tests that select by label
    // can correctly find the element if aria-labelledby is used.
    return `mock-redux-js-nanoid-${id}`;
  },
};

beforeEach(() => {
  // Reset the id before each test is run so that the id does not increment for
  // the whole test file.
  id = 0;
});

export {};
