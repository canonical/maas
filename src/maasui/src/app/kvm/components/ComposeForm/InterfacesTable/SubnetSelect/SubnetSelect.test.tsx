import ComposeForm from "../../ComposeForm";

import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

setupMockServer(
  zoneResolvers.listZones.handler(),
  poolsResolvers.listPools.handler()
);

const renderComposeForm = async (state: RootState, pod: Pod) => {
  const view = renderWithProviders(<ComposeForm hostId={pod.id} />, {
    initialEntries: [`/kvm/${pod.id}`],
    state,
  });
  await waitFor(() => {
    expect(zoneResolvers.listZones.resolved).toBeTruthy();
  });
  return view;
};

describe("SubnetSelect", () => {
  let initialState: RootState;

  beforeEach(() => {
    const pod = factory.podDetails({ id: 1 });

    initialState = factory.rootState({
      domain: factory.domainState({
        loaded: true,
      }),
      fabric: factory.fabricState({
        loaded: true,
      }),
      general: factory.generalState({
        powerTypes: factory.powerTypesState({
          data: [factory.powerType()],
          loaded: true,
        }),
      }),
      pod: factory.podState({
        items: [pod],
        loaded: true,
        statuses: { [pod.id]: factory.podStatus() },
      }),
      space: factory.spaceState({
        loaded: true,
      }),
      subnet: factory.subnetState({
        loaded: true,
      }),
      vlan: factory.vlanState({
        loaded: true,
      }),
    });
  });

  it("groups subnets by space if a space is not yet selected", async () => {
    const spaces = [
      factory.space({ name: "Outer" }),
      factory.space({ name: "Safe" }),
    ];
    const subnets = [
      factory.subnet({ space: spaces[0].id, vlan: 1, name: "sub1" }),
      factory.subnet({ space: spaces[1].id, vlan: 1, name: "sub2" }),
      factory.subnet({ space: spaces[0].id, vlan: 1, name: "sub3" }),
    ];
    const pod = factory.podDetails({
      attached_vlans: [1],
      boot_vlans: [1],
      id: 1,
    });
    const state = { ...initialState };
    state.pod.items = [pod];
    state.space.items = spaces;
    state.subnet.items = subnets;

    await renderComposeForm(state, pod);

    await waitFor(() =>
      screen.getByRole("button", { name: "Define (optional)" })
    );

    // Click "Define" button
    await userEvent.click(
      screen.getByRole("button", { name: "Define (optional)" })
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Space" }),
      ""
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Select subnet..." })
    );

    const spaceGroups = screen.getByLabelText("submenu").children;

    expect(spaceGroups).toHaveLength(5);
    expect(spaceGroups[0]).toHaveTextContent("Space: Outer");
    expect(spaceGroups[1]).toHaveTextContent("sub1");
    expect(spaceGroups[2]).toHaveTextContent("sub3");
    expect(spaceGroups[3]).toHaveTextContent("Space: Safe");
    expect(spaceGroups[4]).toHaveTextContent("sub2");
  });

  it("filters subnets by selected space", async () => {
    const space = factory.space({ id: 0, name: "Outer" });
    const [subnetInSpace, subnetNotInSpace] = [
      factory.subnet({ space: space.id, vlan: 1, name: "sub1" }),
      factory.subnet({ space: null, vlan: 1, name: "sub2" }),
    ];
    const pod = factory.podDetails({
      attached_vlans: [1],
      boot_vlans: [1],
      id: 1,
    });
    const state = { ...initialState };
    state.pod.items = [pod];
    state.space.items = [space];
    state.subnet.items = [subnetInSpace, subnetNotInSpace];

    await renderComposeForm(state, pod);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Define (optional)" })
      ).toBeInTheDocument();
    });
    // Click "Define" button
    await userEvent.click(
      screen.getByRole("button", { name: "Define (optional)" })
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Space" }),
      ""
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Select subnet..." })
    );

    let spaceGroups = screen.getByLabelText("submenu").children;

    expect(spaceGroups[0]).toHaveTextContent("Space: Outer");
    expect(spaceGroups[1]).toHaveTextContent("sub1");
    expect(spaceGroups[2]).toHaveTextContent("No space");
    expect(spaceGroups[3]).toHaveTextContent("sub2");
    expect(spaceGroups).toHaveLength(4);

    // Choose the space in state from the dropdown
    // Only the subnet in the selected space should be available
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Space" }),
      "0"
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Select subnet..." })
    );

    spaceGroups = screen.getByLabelText("submenu").children;

    expect(spaceGroups).toHaveLength(1);
    expect(spaceGroups[0]).toHaveTextContent("sub1");
  });

  it("shows an error if multiple interfaces defined without at least one PXE network", async () => {
    const fabric = factory.fabric();
    const space = factory.space();
    const pxeVlan = factory.vlan({
      fabric: fabric.id,
      id: 1,
      name: "test-vlan-1",
    });
    const nonPxeVlan = factory.vlan({ fabric: fabric.id, id: 2 });
    const pxeSubnet = factory.subnet({ name: "pxe", vlan: pxeVlan.id });
    const nonPxeSubnet = factory.subnet({
      name: "non-pxe",
      vlan: nonPxeVlan.id,
    });
    const pod = factory.podDetails({
      attached_vlans: [pxeVlan.id, nonPxeVlan.id],
      boot_vlans: [pxeVlan.id],
      id: 1,
    });
    const state = { ...initialState };
    state.pod.items = [pod];
    state.space.items = [space];
    state.subnet.items = [pxeSubnet, nonPxeSubnet];
    state.vlan.items = [pxeVlan, nonPxeVlan];

    await renderComposeForm(state, pod);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Define (optional)" })
      ).toBeInTheDocument();
    });

    // Click "Define" button
    await userEvent.click(
      screen.getByRole("button", { name: "Define (optional)" })
    );

    // Add a second interface
    await userEvent.click(
      screen.getByRole("button", { name: "Add interface" })
    );

    // Select non-PXE network for the first interface
    await userEvent.selectOptions(
      screen.getAllByRole("combobox", { name: "Space" })[0],
      ""
    );
    await userEvent.click(
      screen.getAllByRole("button", { name: "Select subnet..." })[0]
    );
    await userEvent.click(
      within(screen.getByLabelText("submenu")).getByRole("button", {
        name: /non-pxe/i,
      })
    );

    // Select non-PXE network for the second interface - error should be present.
    await userEvent.selectOptions(
      screen.getAllByRole("combobox", { name: "Space" })[1],
      ""
    );
    await userEvent.click(
      screen.getAllByRole("button", { name: "Select subnet..." })[0]
    );
    await userEvent.click(
      within(screen.getByLabelText("submenu")).getByRole("button", {
        name: /non-pxe/i,
      })
    );
    expect(screen.getByTestId("no-pxe")).toHaveTextContent(
      "Select at least 1 PXE network when creating multiple interfaces."
    );

    // Select PXE network for the second interface - error should be removed.
    await userEvent.click(screen.getAllByText("non-pxe")[1]);
    await userEvent.click(
      within(screen.getByLabelText("submenu")).getByRole("button", {
        name: /pxe test-vlan-1/i,
      })
    );
    expect(screen.queryByTestId("no-pxe")).not.toBeInTheDocument();

    // Remove second interface with PXE network - error should still not show.
    await userEvent.click(screen.getAllByTestId("delete-interface")[1]);
    expect(screen.queryByTestId("no-pxe")).not.toBeInTheDocument();
  });
});
