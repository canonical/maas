import SpaceSubnetsTable from "./SpaceSubnetsTable";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

const getRootState = () =>
  factory.rootState({
    vlan: factory.vlanState({
      loaded: true,
      loading: false,
      items: [factory.vlan({ id: 2, fabric: 1 })],
    }),
    space: factory.spaceState({
      loaded: true,
      loading: false,
      items: [factory.space({ id: 3 })],
    }),
    subnet: factory.subnetState({
      loaded: true,
      loading: false,
      items: [factory.subnet({ id: 4, vlan: 2 })],
    }),
    fabric: factory.fabricState({
      items: [factory.fabric({ vlan_ids: [2] })],
      loaded: true,
      loading: false,
    }),
  });

it("displays a message when there are no subnets", async () => {
  const state = getRootState();
  const space = factory.space({ id: 1, subnet_ids: [4], vlan_ids: [2] });
  state.space.items = [space];

  renderWithProviders(<SpaceSubnetsTable space={space} />, { state });

  expect(
    screen.getByText("There are no subnets on this space.")
  ).toBeInTheDocument();
});

it("displays subnet details correctly", async () => {
  const space = factory.space({ id: 1, subnet_ids: [4], vlan_ids: [2] });
  const state = getRootState();
  state.subnet.items = [
    factory.subnet({
      id: 4,
      vlan: 2,
      space: 1,
      name: "test-subnet",
      statistics: factory.subnetStatistics({ available_string: "50%" }),
    }),
  ];
  state.fabric.items = [
    factory.fabric({ id: 1, name: "test-fabric", vlan_ids: [2] }),
  ];

  renderWithProviders(<SpaceSubnetsTable space={space} />, { state });

  ["Subnet", "Available IPs", "VLAN", "Fabric"].forEach((column) => {
    expect(
      screen.getByRole("columnheader", {
        name: new RegExp(`^${column}`, "i"),
      })
    ).toBeInTheDocument();
  });
});
