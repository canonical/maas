import StorageCards, {
  updateCardSize,
  MEDIUM_MIN_WIDTH,
  LARGE_MIN_WIDTH,
} from "./StorageCards";

import { COLOURS } from "@/app/base/constants";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("StorageCards", () => {
  it("correctly calculates meter width", () => {
    const storagePoolResource = factory.podStoragePoolResource({
      allocated_tracked: 20,
      allocated_other: 30,
      total: 100,
    });
    renderWithProviders(<StorageCards pools={{ pool: storagePoolResource }} />);
    const expectedBg = `linear-gradient(
      to right,
      ${COLOURS.LINK} 0,
      ${COLOURS.LINK} 20%,
      ${COLOURS.POSITIVE} 20%,
      ${COLOURS.POSITIVE} 50%,
      ${COLOURS.LINK_FADED} 50%,
      ${COLOURS.LINK_FADED} 100%
    )`;
    expect(screen.getByTestId("storage-card-meter")).toHaveStyle(
      `background-image: ${expectedBg}`
    );
  });

  describe("updateCardSize", () => {
    it("sets card size to large if all cards can fit on one row", () => {
      const setCardSize = vi.fn();
      updateCardSize(LARGE_MIN_WIDTH * 3, 3, setCardSize);
      updateCardSize(LARGE_MIN_WIDTH * 3 + 1, 3, setCardSize);
      updateCardSize(LARGE_MIN_WIDTH * 3 - 1, 3, setCardSize);
      expect(setCardSize.mock.calls).toEqual([
        ["large"],
        ["large"],
        ["medium"],
      ]);
    });

    it("sets card size to medium if all cards can fit on two rows, but not one", () => {
      const setCardSize = vi.fn();
      updateCardSize(MEDIUM_MIN_WIDTH * 3, 6, setCardSize);
      updateCardSize(MEDIUM_MIN_WIDTH * 3 + 1, 6, setCardSize);
      updateCardSize(MEDIUM_MIN_WIDTH * 3 - 1, 6, setCardSize);
      expect(setCardSize.mock.calls).toEqual([
        ["medium"],
        ["medium"],
        ["small"],
      ]);
    });

    it("sets card size to small if all cards cannot fit on two rows", () => {
      const setCardSize = vi.fn();
      updateCardSize(MEDIUM_MIN_WIDTH, 3, setCardSize);
      updateCardSize(MEDIUM_MIN_WIDTH * 3, 7, setCardSize);
      expect(setCardSize.mock.calls).toEqual([["small"], ["small"]]);
    });
  });
});
