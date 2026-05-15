import { expect } from "vitest";

declare global {
  // This is the simplest way of making sure our custom matcher is usable
  // and doesn't cause lint errors.
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace jest {
    interface Matchers<R> {
      toBeAriaDisabled(): R;
    }
  }
}

// `received` is likely an HTML element but this is not guarenteed
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toBeAriaDisabled(received: any) {
  const isDisabled =
    received.disabled || received.getAttribute("aria-disabled") === "true";

  if (isDisabled) {
    return {
      message: () => `expected element not to be disabled, but it is`,
      pass: true,
    };
  } else {
    return {
      message: () => `expected element to be disabled, but it is not`,
      pass: false,
    };
  }
}

expect.extend({
  toBeAriaDisabled,
});
