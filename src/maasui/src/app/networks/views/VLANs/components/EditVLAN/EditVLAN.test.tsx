import EditVLAN from "./EditVLAN";

import type { RootState } from "@/app/store/root/types";
import { vlanActions } from "@/app/store/vlan";
import type { VLAN } from "@/app/store/vlan/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  within,
  renderWithProviders,
} from "@/testing/utils";

describe("EditVLAN", () => {
  let state: RootState;
  let vlan: VLAN;

  beforeEach(() => {
    const fabric = factory.fabric({ id: 22, name: "fabric1" });
    const space = factory.space({ id: 23, name: "space1" });
    vlan = factory.vlan({
      description: "I'm a little VLAN",
      fabric: 22,
      mtu: 5432,
      name: "vlan-333",
      space: space.id,
      vid: 1010,
    });
    state = factory.rootState({
      fabric: factory.fabricState({ items: [fabric, factory.fabric()] }),
      space: factory.spaceState({ items: [space, factory.space()] }),
      vlan: factory.vlanState({ items: [vlan] }),
    });
  });

  it("displays a spinner when data is loading", () => {
    state.vlan.items = [];
    renderWithProviders(<EditVLAN id={vlan.id} />, { state });
    expect(screen.getByTestId("Spinner")).toBeInTheDocument();
  });

  it("initialises the vlan details", () => {
    renderWithProviders(<EditVLAN id={vlan.id} />, { state });
    expect(screen.getByRole("textbox", { name: "VID" })).toHaveAttribute(
      "value",
      vlan.vid.toString()
    );
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveAttribute(
      "value",
      vlan.name
    );
    expect(screen.getByRole("textbox", { name: "MTU" })).toHaveAttribute(
      "value",
      vlan.mtu.toString()
    );
    expect(
      screen.getByRole("textbox", { name: "Description" }).textContent
    ).toBe(vlan.description);
    expect(
      within(screen.getByRole("combobox", { name: "Space" })).getByRole(
        "option",
        { name: "space1", selected: true }
      )
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("combobox", { name: "Fabric" })).getByRole(
        "option",
        { name: "fabric1", selected: true }
      )
    ).toBeInTheDocument();
  });

  it("dispatches an action to update a VLAN", async () => {
    const { store } = renderWithProviders(<EditVLAN id={vlan.id} />, { state });
    const nameField = screen.getByRole("textbox", { name: "Name" });
    await userEvent.clear(nameField);
    await userEvent.type(nameField, "new-name");
    await userEvent.click(screen.getByRole("button", { name: "Save summary" }));
    const expected = vlanActions.update({
      description: vlan.description,
      fabric: vlan.fabric,
      id: vlan.id,
      mtu: vlan.mtu,
      name: "new-name",
      space: vlan.space,
      vid: vlan.vid,
    });
    await waitFor(() => {
      expect(
        store.getActions().find((action) => action.type === expected.type)
      ).toStrictEqual(expected);
    });
  });

  it("allows the space to be unset", async () => {
    renderWithProviders(<EditVLAN id={vlan.id} />, { state });
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Space" }),
      ""
    );
    await waitFor(() => {
      expect(
        within(screen.getByRole("combobox", { name: "Space" })).getByRole(
          "option",
          { name: "No space" }
        )
      ).toBeInTheDocument();
    });
  });
});
