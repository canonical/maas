import "@testing-library/react";
import "@testing-library/jest-dom";
import { URLSearchParams } from "node:url";

import { vi, beforeAll } from "vitest";
import createFetchMock from "vitest-fetch-mock";

import "./testing/customMatchers";

const fetchMocker = createFetchMock(vi);

fetchMocker.enableMocks();
const originalObserver = window.ResizeObserver;
const originalScrollIntoView = window.HTMLElement.prototype.scrollIntoView;

beforeAll(() => {
  // disable act warnings
  global.IS_REACT_ACT_ENVIRONMENT = false;

  // Use URLSearchParams from node:url, since vitest uses Request and fetch from node while jsdom provides URLSearchParams https://github.com/vitest-dev/vitest/issues/7906
  Object.defineProperties(globalThis, {
    URLSearchParams: { value: URLSearchParams },
  });
});

// Mock Web Animations API - not implemented in jsdom but used by
// @canonical/react-components ToastNotification/Animate
Element.prototype.animate = vi.fn().mockReturnValue({
  finished: Promise.resolve(),
  cancel: vi.fn(),
  finish: vi.fn(),
  pause: vi.fn(),
  play: vi.fn(),
  reverse: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
});

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

beforeEach(() => {
  // mock ResizeObserver for MainToolbar
  window.ResizeObserver = vi.fn(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
  }));

  // mock scrollIntoView for FormikFormContent
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  window.ResizeObserver = originalObserver;
  window.HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
});
