import AddInterface from "./AddInterface";

import type { RootState } from "@/app/store/root/types";
import { NetworkLinkMode } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("AddInterface", () => {
  let state: RootState;
  const fabric = factory.fabric();
  const vlan = factory.vlan({
    id: 28,
    fabric: fabric.id,
    vid: 2,
    name: "vlan-name",
    external_dhcp: null,
    dhcp_on: true,
  });
  beforeEach(() => {
    state = factory.rootState({
      fabric: factory.fabricState({
        items: [fabric, factory.fabric()],
        loaded: true,
      }),
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
      subnet: factory.subnetState({
        items: [factory.subnet(), factory.subnet()],
        loaded: true,
      }),
      vlan: factory.vlanState({
        items: [vlan],
        loaded: true,
      }),
    });
  });

  it("fetches the necessary data on load", async () => {
    const { store } = renderWithProviders(<AddInterface systemId="abc123" />, {
      state,
    });
    const expectedActions = ["fabric/fetch", "vlan/fetch"];
    expectedActions.forEach((expectedAction) => {
      expect(
        store.getActions().some((action) => action.type === expectedAction)
      );
    });
  });

  it("displays a spinner when data is loading", async () => {
    state.vlan.loaded = false;
    state.fabric.loaded = false;
    renderWithProviders(<AddInterface systemId="abc123" />, {
      state,
    });
    expect(screen.getByText("Loading")).toBeInTheDocument();
  });

  it("correctly dispatches actions to add a physical interface", async () => {
    state.machine.selected = { items: ["abc123", "def456"] };
    const { store } = renderWithProviders(<AddInterface systemId="abc123" />, {
      state,
    });
    await userEvent.type(
      screen.getByRole("textbox", { name: "MAC address" }),
      "28:21:c6:b9:1b:22"
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Fabric" }),
      "1"
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Subnet" }),
      ""
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Save interface" })
    );

    expect(
      store
        .getActions()
        .find((action) => action.type === "machine/createPhysical")
    ).toStrictEqual({
      type: "machine/createPhysical",
      meta: {
        model: "machine",
        method: "create_physical",
      },
      payload: {
        params: {
          fabric: "1",
          mac_address: "28:21:c6:b9:1b:22",
          mode: NetworkLinkMode.LINK_UP,
          name: "eth0",
          system_id: "abc123",
          tags: [],
          vlan: `${vlan.id}`,
        },
      },
    });
  });
});
