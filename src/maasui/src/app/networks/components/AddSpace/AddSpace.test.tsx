import AddSpace from "./AddSpace";

import { spaceActions } from "@/app/store/space";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  mockSidePanel,
  renderWithProviders,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("AddSpace", () => {
  it("runs closeSidePanel function when the cancel button is clicked", async () => {
    renderWithProviders(<AddSpace />);

    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls create space on save click", async () => {
    const { store } = renderWithProviders(<AddSpace />);

    const name = "Space name";

    await userEvent.type(screen.getByRole("textbox", { name: /Name/ }), name);
    await userEvent.click(screen.getByRole("button", { name: /Save space/i }));

    await waitFor(() => {
      expect(store.getActions()).toStrictEqual([
        spaceActions.cleanup(),
        spaceActions.create({ name }),
      ]);
    });
  });

  it("displays error message when create space fails", async () => {
    const state = factory.rootState({
      space: factory.spaceState({ errors: "Uh oh!" }),
    });

    renderWithProviders(<AddSpace />, { state });

    await userEvent.type(screen.getByRole("textbox", { name: /Name/ }), "test");

    await userEvent.click(screen.getByRole("button", { name: /Save space/i }));

    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
