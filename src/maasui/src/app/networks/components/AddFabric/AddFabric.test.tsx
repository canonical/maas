import AddFabric from "./AddFabric";

import { fabricActions } from "@/app/store/fabric";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  mockSidePanel,
  renderWithProviders,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("AddFabric", () => {
  it("runs closeSidePanel function when the cancel button is clicked", async () => {
    renderWithProviders(<AddFabric />);

    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls create fabric on save click", async () => {
    const { store } = renderWithProviders(<AddFabric />);

    const name = "Fabric name";
    const description = "Description";

    await userEvent.type(screen.getByRole("textbox", { name: /Name/ }), name);
    await userEvent.type(
      screen.getByRole("textbox", { name: /Description/ }),
      description
    );
    await userEvent.click(screen.getByRole("button", { name: /Save fabric/i }));

    await waitFor(() => {
      expect(store.getActions()).toStrictEqual([
        fabricActions.cleanup(),
        fabricActions.create({ name, description }),
      ]);
    });
  });

  it("displays error message when create fabric fails", async () => {
    const state = factory.rootState({
      fabric: factory.fabricState({ errors: "Uh oh!" }),
    });

    renderWithProviders(<AddFabric />, { state });

    await userEvent.type(screen.getByRole("textbox", { name: /Name/ }), "test");

    await userEvent.click(screen.getByRole("button", { name: /Save fabric/i }));

    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
