import { render, renderHook, screen, waitFor } from "@testing-library/react";
import type { Mock } from "vitest";

import {
  useCycled,
  useGlobalKeyShortcut,
  useId,
  useOnKeyPressed,
  usePreviousPersistent,
  useProcessing,
  useScrollOnRender,
  useScrollToTop,
  useWindowTitle,
} from "./base";

import {
  renderHookWithMockStore,
  renderHookWithProviders,
  userEvent,
} from "@/testing/utils";

const mockUseLocationValue = {
  pathname: "/original-pathname",
  search: "",
  hash: "",
  state: null,
};
vi.mock("react-router", () => ({
  ...vi.importActual("react-router"),
  useLocation: () => mockUseLocationValue,
}));

describe("useWindowTitle", () => {
  it("sets the window title", () => {
    const { rerender } = renderHookWithMockStore(() => {
      useWindowTitle("Test");
    });
    expect(document.title).toBe("Test | MAAS");
    rerender();
    expect(document.title).toBe("Test | MAAS");
  });
  it("keeps the window title unchanged on unmount", () => {
    const { unmount } = renderHookWithMockStore(() => {
      useWindowTitle("Test");
    });
    expect(document.title).toBe("Test | MAAS");
    unmount();
    expect(document.title).toBe("Test | MAAS");
  });
});

describe("useScrollOnRender", () => {
  let html: HTMLHtmlElement | null;
  let scrollToSpy: Mock;
  let targetNode: HTMLElement;

  beforeEach(() => {
    global.innerHeight = 500;
    // eslint-disable-next-line testing-library/no-node-access
    html = document.querySelector("html");
    scrollToSpy = vi.fn();
    global.scrollTo = scrollToSpy;
    targetNode = document.createElement("div");
  });

  afterEach(() => {
    if (html) {
      html.scrollTop = 0;
    }
  });

  it("does not scroll if the target is on screen", () => {
    if (html) {
      html.scrollTop = 10;
    }
    const { result } = renderHook(() => useScrollOnRender());
    targetNode.getBoundingClientRect = () => ({ y: 10 }) as DOMRect;
    result.current(targetNode);
    expect(scrollToSpy).not.toHaveBeenCalled();
  });

  it("scrolls if the target is off the bottom of the screen", () => {
    if (html) {
      html.scrollTop = 100;
    }
    const { result } = renderHook(() => useScrollOnRender());
    targetNode.getBoundingClientRect = () => ({ y: 1000 }) as DOMRect;
    result.current(targetNode);
    expect(scrollToSpy).toHaveBeenCalledWith({
      top: 1000,
      left: 0,
      behavior: "smooth",
    });
  });

  it("scrolls if the target is off the top of the screen", () => {
    if (html) {
      html.scrollTop = 1000;
    }
    const { result } = renderHook(() => useScrollOnRender());
    targetNode.getBoundingClientRect = () => ({ y: 10 }) as DOMRect;
    result.current(targetNode);
    expect(scrollToSpy).toHaveBeenCalledWith({
      top: 10,
      left: 0,
      behavior: "smooth",
    });
  });

  it("scrolls if the target is partially off the bottom of the screen", () => {
    if (html) {
      html.scrollTop = 100;
    }
    const { result } = renderHook(() => useScrollOnRender());
    targetNode.getBoundingClientRect = () =>
      ({ height: 400, y: 400 }) as DOMRect;
    result.current(targetNode);
    expect(scrollToSpy).toHaveBeenCalledWith({
      top: 400,
      left: 0,
      behavior: "smooth",
    });
  });
});

describe("useCycled", () => {
  it("can handle the initial state", () => {
    const onCycled = vi.fn();
    const { result } = renderHook(() => useCycled(false, onCycled));
    const [hasCycled] = result.current;
    expect(hasCycled).toBe(false);
    expect(onCycled).not.toHaveBeenCalled();
  });

  it("can handle rerenders when the value has not cycled", () => {
    const onCycled = vi.fn();
    const { result, rerender } = renderHook(
      ({ state }) => useCycled(state, onCycled),
      {
        initialProps: { state: false },
      }
    );
    rerender({ state: false });
    const [hasCycled] = result.current;
    expect(hasCycled).toBe(false);
    expect(onCycled).not.toHaveBeenCalled();
  });

  it("can handle rerenders when the value has cycled", () => {
    const onCycled = vi.fn();
    const { result, rerender } = renderHook(
      ({ state }) => useCycled(state, onCycled),
      {
        initialProps: { state: false },
      }
    );
    rerender({ state: true });
    const [hasCycled] = result.current;
    expect(hasCycled).toBe(true);
    expect(onCycled).toHaveBeenCalled();
  });

  it("can reset the cycle", async () => {
    const onCycled = vi.fn();
    const { result, rerender } = renderHook(
      ({ state }) => useCycled(state, onCycled),
      {
        initialProps: { state: false },
      }
    );
    rerender({ state: true });
    let [hasCycled, resetCycle] = result.current;
    expect(hasCycled).toBe(true);
    expect(onCycled).toHaveBeenCalledTimes(1);
    resetCycle();
    await waitFor(() => {
      [hasCycled, resetCycle] = result.current;
      expect(hasCycled).toBe(false);
    });
    // The onCycle function should not get called when it resets.
    expect(onCycled).toHaveBeenCalledTimes(1);
  });

  it("can handle values that have cycled after a reset", async () => {
    const onCycled = vi.fn();
    const { result, rerender } = renderHook(
      ({ state }) => useCycled(state, onCycled),
      {
        initialProps: { state: false },
      }
    );
    // Cycle the value to true:
    rerender({ state: true });
    let [hasCycled, resetCycle] = result.current;
    expect(hasCycled).toBe(true);
    // Reset to false:
    resetCycle();
    rerender({ state: false });
    await waitFor(() => {
      [hasCycled, resetCycle] = result.current;
      expect(hasCycled).toBe(false);
    });
    // Cycle the value back to true:
    rerender({ state: true });
    [hasCycled, resetCycle] = result.current;
    expect(hasCycled).toBe(true);
    expect(onCycled).toHaveBeenCalledTimes(2);
  });
});

describe("useProcessing", () => {
  it("handles whether processing has completed", () => {
    const onComplete = vi.fn();
    const onError = vi.fn();
    // Start with a count of 0
    const { rerender, result } = renderHook(
      ({ processingCount }) =>
        useProcessing({ onComplete, onError, processingCount }),
      { initialProps: { processingCount: 0 } }
    );
    expect(onComplete).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
    expect(result.current).toBe(false);

    // Start processing with a count of 1 - processing should not be complete.
    rerender({ processingCount: 1 });
    expect(onComplete).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
    expect(result.current).toBe(false);

    // Count down to 0 - processing should be complete and onComplete should run.
    rerender({ processingCount: 0 });
    expect(onComplete).toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
    expect(result.current).toBe(true);
  });

  it("handles errors occurring while processing", () => {
    const onComplete = vi.fn();
    const onError = vi.fn();
    // Start with a count of 0
    const { rerender, result } = renderHook(
      ({ hasErrors, processingCount }) =>
        useProcessing({ hasErrors, onComplete, onError, processingCount }),
      { initialProps: { hasErrors: false, processingCount: 0 } }
    );
    expect(onComplete).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
    expect(result.current).toBe(false);

    // Start processing with a count of 1 - processing should not be complete.
    rerender({ hasErrors: false, processingCount: 1 });
    expect(onComplete).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
    expect(result.current).toBe(false);

    // Count down to 0 - processing should not be complete, onComplete should
    // not run but onError should have run.
    rerender({ hasErrors: true, processingCount: 0 });
    expect(onComplete).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalled();
    expect(result.current).toBe(false);
  });
});

describe("getId", () => {
  it("generates the id on first render", () => {
    const { result, rerender } = renderHook(() => useId());
    expect(result.current).toBeTruthy();
    const previousResult = result;
    rerender();
    expect(result.current).toEqual(previousResult.current);
  });
});

describe("useScrollToTop", () => {
  it("scrolls to the top of the page on pathname change", () => {
    const scrollToSpy = vi.fn();
    global.scrollTo = scrollToSpy;
    const { rerender } = renderHook(() => {
      useScrollToTop();
    });

    expect(scrollToSpy).toHaveBeenCalledWith(0, 0);
    expect(scrollToSpy).toHaveBeenCalledTimes(1);

    mockUseLocationValue.pathname = "/new-pathname";
    rerender();

    expect(scrollToSpy).toHaveBeenCalledTimes(2);
  });

  it("does not scroll to the top of the page if pathname stays the same", () => {
    const scrollToSpy = vi.fn();
    global.scrollTo = scrollToSpy;
    renderHookWithProviders(() => {
      useScrollToTop();
    });

    expect(scrollToSpy).toHaveBeenCalledWith(0, 0);
    expect(scrollToSpy).toHaveBeenCalledTimes(1);

    expect(scrollToSpy).toHaveBeenCalledTimes(1);
  });
});

describe("usePreviousPersistent", () => {
  it("should return null on initial render", () => {
    const { result } = renderHook(() => usePreviousPersistent({ a: "b" }));

    expect(result.current).toBeNull();
  });

  it("persists previous values on re-render", () => {
    const { rerender, result } = renderHook(
      (state) => usePreviousPersistent(state),
      {
        initialProps: 1,
      }
    );

    rerender(2);
    expect(result.current).toEqual(1);
    rerender(3);
    expect(result.current).toEqual(2);
  });
});

describe("useOnKeyPressed", () => {
  it("calls the callback when the specified key is pressed", () => {
    const callback = vi.fn();
    renderHook(() => {
      useOnKeyPressed("Enter", callback);
    });

    const event = new KeyboardEvent("keydown", { key: "Enter" });
    document.dispatchEvent(event);

    expect(callback).toHaveBeenCalledWith(event);
  });

  it("does not call the callback for other keys", () => {
    const onAfterPressed = vi.fn();
    renderHook(() => {
      useOnKeyPressed("Enter", onAfterPressed);
    });

    const event = new KeyboardEvent("keydown", { key: "Escape" });
    document.dispatchEvent(event);

    expect(onAfterPressed).not.toHaveBeenCalled();
  });
});

describe("useGlobalKeyShortcut", () => {
  const callback = vi.fn();

  const TestInput = () => {
    useGlobalKeyShortcut("/", callback);
    return <input aria-label="Email" name="email" type="text" />;
  };

  const TestTextarea = () => {
    useGlobalKeyShortcut("/", callback);
    return <textarea aria-label="Description" name="description" />;
  };

  it("calls the callback when the specified key is pressed", () => {
    renderHook(() => {
      useGlobalKeyShortcut("/", callback);
    });

    const event = new KeyboardEvent("keydown", { key: "/" });
    document.dispatchEvent(event);

    expect(callback).toHaveBeenCalledWith(event);
  });

  it("does not call the callback for other keys", () => {
    renderHook(() => {
      useGlobalKeyShortcut("/", callback);
    });

    const event = new KeyboardEvent("keydown", { key: "Escape" });
    document.dispatchEvent(event);

    expect(callback).not.toHaveBeenCalled();
  });

  it("does not call the callback if an input element is focused", async () => {
    render(<TestInput />);

    await userEvent.type(screen.getByRole("textbox", { name: "Email" }), "/");

    expect(callback).not.toHaveBeenCalled();
  });

  it("does not call the callback if a textarea element is focused", async () => {
    render(<TestTextarea />);

    await userEvent.type(
      screen.getByRole("textbox", { name: "Description" }),
      "/"
    );

    expect(callback).not.toHaveBeenCalled();
  });
});
