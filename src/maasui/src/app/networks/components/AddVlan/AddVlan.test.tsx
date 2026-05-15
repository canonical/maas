import AddVlan from "./AddVlan";

import { vlanActions } from "@/app/store/vlan";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  mockSidePanel,
  renderWithProviders,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("AddVlan", () => {
  const vid = 123;
  const name = "VLAN name";
  const space = { id: 1, name: "space1" };
  const fabric = { id: 1, name: "fabric1" };

  const state = factory.rootState({
    space: factory.spaceState({
      items: [factory.space(space)],
      loaded: true,
    }),
    fabric: factory.fabricState({
      items: [factory.fabric(fabric)],
      loaded: true,
    }),
  });

  it("displays validation messages for VID", async () => {
    renderWithProviders(<AddVlan />);

    const VidTextBox = screen.getByRole("textbox", { name: /VID/ });
    const submitButton = screen.getByRole("button", { name: /Save VLAN/i });
    const errorMessage = /must be a numeric value/;

    await userEvent.type(VidTextBox, "abc");
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });

    await userEvent.clear(VidTextBox);
    await userEvent.type(VidTextBox, "123");

    await waitFor(() => {
      expect(screen.queryByText(errorMessage)).not.toBeInTheDocument();
    });

    await userEvent.clear(VidTextBox);
    await userEvent.type(VidTextBox, "99999");

    await waitFor(() => {
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });
  });

  it("runs closeSidePanel function when the cancel button is clicked", async () => {
    renderWithProviders(<AddVlan />);

    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls create vlan on save click", async () => {
    const { store } = renderWithProviders(<AddVlan />, { state });

    await userEvent.type(
      screen.getByRole("textbox", { name: /VID/ }),
      `${vid}`
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /Name/ }),
      `${name}`
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Fabric" }),
      fabric.name
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Space" }),
      space.name
    );

    await userEvent.click(screen.getByRole("button", { name: /Save VLAN/i }));

    const expectedActions = [
      vlanActions.cleanup(),
      vlanActions.create({
        vid,
        name,
        fabric: fabric.id,
        space: space.id,
      }),
    ];
    await waitFor(() => {
      const actualActions = store.getActions();
      expectedActions.forEach((expectedAction) => {
        expect(
          actualActions.find(({ type }) => type === expectedAction.type)
        ).toStrictEqual(expectedAction);
      });
    });
  });

  it("displays error message when create vlan fails", async () => {
    const errorState = factory.rootState({
      ...state,
      vlan: factory.vlanState({ errors: "Uh oh!" }),
    });

    renderWithProviders(<AddVlan />, { state: errorState });

    await userEvent.type(
      screen.getByRole("textbox", { name: /VID/ }),
      `${vid}`
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /Name/ }),
      `${name}`
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Fabric" }),
      fabric.name
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Space" }),
      space.name
    );

    await userEvent.click(screen.getByRole("button", { name: /Save VLAN/i }));

    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
