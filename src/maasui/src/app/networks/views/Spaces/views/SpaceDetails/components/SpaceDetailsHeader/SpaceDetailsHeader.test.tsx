import { waitFor } from "@testing-library/react";

import SpaceDetailsHeader from "./SpaceDetailsHeader";

import { DeleteSpace } from "@/app/networks/views/Spaces/components";
import type { RootState } from "@/app/store/root/types";
import type { Space } from "@/app/store/space/types";
import * as factory from "@/testing/factories";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
} from "@/testing/utils";

let state: RootState;
let space: Space;

const { mockOpen } = await mockSidePanel();

describe("SpaceDetailsHeader", () => {
  beforeEach(() => {
    space = factory.space({
      id: 1,
      name: "space-1",
      description: "space 1 description",
    });
    state = factory.rootState({
      space: factory.spaceState({
        items: [space],
        loading: false,
      }),
    });
  });

  it("shows the space name as the section title", () => {
    renderWithProviders(<SpaceDetailsHeader space={space} />, {
      state,
    });

    expect(screen.getByTestId("section-header-title")).toHaveTextContent(
      "space-1"
    );
  });

  it("calls a function to open the Delete form when the button is clicked", async () => {
    renderWithProviders(<SpaceDetailsHeader space={space} />, {
      state,
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Delete space" })
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Delete space" }));

    expect(mockOpen).toHaveBeenCalledWith({
      component: DeleteSpace,
      title: "Delete space",
      props: { id: space.id },
    });
  });
});
