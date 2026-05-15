import ColumnToggle from "./ColumnToggle";

import { userEvent, screen, renderWithProviders } from "@/testing/utils";

const DOM_RECT = {
  height: 0,
  width: 0,
  x: 0,
  y: 0,
  bottom: 0,
  left: 0,
  right: 0,
  toJSON: vi.fn(),
};

describe("ColumnToggle ", () => {
  beforeEach(() => {
    vi.spyOn(window, "scrollTo");
  });

  it("calls the close function when expanded", async () => {
    const onClose = vi.fn();
    renderWithProviders(
      <ColumnToggle
        isExpanded={true}
        label="maas.local"
        onClose={onClose}
        onOpen={vi.fn()}
      />
    );

    await userEvent.click(screen.getByRole("button"));

    expect(onClose).toHaveBeenCalled();
  });

  it("calls the open function when not expanded", async () => {
    const onOpen = vi.fn();
    renderWithProviders(
      <ColumnToggle
        isExpanded={false}
        label="maas.local"
        onClose={vi.fn()}
        onOpen={onOpen}
      />
    );

    await userEvent.click(screen.getByRole("button"));

    expect(onOpen).toHaveBeenCalled();
  });

  describe("scroll", () => {
    beforeEach(() => {
      vi.spyOn(window, "requestAnimationFrame").mockImplementation(
        (cb: FrameRequestCallback) => {
          cb(0);
          return 0;
        }
      );
      Object.defineProperty(window, "scrollY", { value: 100 });
    });

    afterEach(() => {
      vi.restoreAllMocks();
      Object.defineProperty(window, "scrollY", { value: 0 });
    });

    afterEach(() => {
      vi.clearAllMocks();
    });

    it("can scroll to a toggle", async () => {
      Element.prototype.getBoundingClientRect = vi.fn(() => ({
        ...DOM_RECT,
        top: -20,
      }));
      renderWithProviders(
        <ColumnToggle
          isExpanded={false}
          label="maas.local"
          onClose={vi.fn()}
          onOpen={vi.fn()}
        />
      );

      await userEvent.click(screen.getByRole("button"));

      expect(window.scrollTo).toHaveBeenCalledWith(0, 80);
    });

    it("does not scroll if the toggle is visible", async () => {
      Element.prototype.getBoundingClientRect = vi.fn(() => ({
        ...DOM_RECT,
        top: 20,
      }));
      renderWithProviders(
        <ColumnToggle
          isExpanded={false}
          label="maas.local"
          onClose={vi.fn()}
          onOpen={vi.fn()}
        />
      );

      await userEvent.click(screen.getByRole("button"));

      expect(window.scrollTo).not.toHaveBeenCalled();
    });
  });
});
