import FabricVLANsTable from "./FabricVLANsTable";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen, within } from "@/testing/utils";

it("renders correct details", () => {
  const fabric = factory.fabric({ id: 1, name: "test-fabric", vlan_ids: [2] });
  const space = factory.space({ id: 3, name: "test-space" });
  const vlan = factory.vlan({ id: 2, fabric: 1, name: "test-vlan", space: 3 });
  const subnet = factory.subnet({ id: 4, vlan: 2, name: "test-subnet" });
  const state = factory.rootState({
    vlan: factory.vlanState({ items: [vlan] }),
    space: factory.spaceState({ items: [space] }),
    subnet: factory.subnetState({ items: [subnet] }),
    fabric: factory.fabricState({ items: [fabric] }),
  });

  renderWithProviders(<FabricVLANsTable fabric={fabric} />, { state });

  expect(
    screen.getByRole("heading", { name: "VLANs on this fabric" })
  ).toBeInTheDocument();

  expect(
    screen.getByRole("columnheader", { name: "VLAN" })
  ).toBeInTheDocument();

  expect(
    screen.getByRole("columnheader", { name: "Subnets" })
  ).toBeInTheDocument();

  expect(
    screen.getByRole("columnheader", { name: "Available" })
  ).toBeInTheDocument();

  expect(
    screen.getByRole("columnheader", { name: "Space" })
  ).toBeInTheDocument();

  expect(
    screen.getByRole("cell", { name: new RegExp(vlan.name) })
  ).toBeInTheDocument();

  expect(
    screen.getByRole("cell", { name: new RegExp(space.name) })
  ).toBeInTheDocument();

  expect(
    screen.getByRole("cell", { name: new RegExp(subnet.name) })
  ).toBeInTheDocument();

  expect(
    screen.getByRole("cell", { name: subnet.statistics.available_string })
  ).toBeInTheDocument();
});

it("handles a VLAN without any subnets", () => {
  const fabric = factory.fabric({ name: "test-fabric", vlan_ids: [1] });
  const space = factory.space({ name: "test-space" });
  const vlan = factory.vlan({
    fabric: fabric.id,
    id: 1,
    name: "test-vlan",
    space: space.id,
  });
  const state = factory.rootState({
    fabric: factory.fabricState({ items: [fabric] }),
    space: factory.spaceState({ items: [space] }),
    subnet: factory.subnetState({ items: [] }),
    vlan: factory.vlanState({ items: [vlan] }),
  });
  renderWithProviders(<FabricVLANsTable fabric={fabric} />, { state });

  expect(screen.getByRole("cell", { name: "No subnets" })).toBeInTheDocument();
});

it("handles a VLAN with multiple subnets", () => {
  const fabric = factory.fabric({ name: "test-fabric", vlan_ids: [1] });
  const space = factory.space({ name: "test-space" });
  const vlan = factory.vlan({
    fabric: fabric.id,
    id: 1,
    name: "test-vlan",
    space: space.id,
  });
  const subnets = [
    factory.subnet({
      name: "test-subnet-1",
      statistics: factory.subnetStatistics({ available_string: "66%" }),
      vlan: vlan.id,
    }),
    factory.subnet({
      name: "test-subnet-2",
      statistics: factory.subnetStatistics({ available_string: "77%" }),
      vlan: vlan.id,
    }),
  ];

  const state = factory.rootState({
    fabric: factory.fabricState({ items: [fabric] }),
    space: factory.spaceState({ items: [space] }),
    subnet: factory.subnetState({ items: subnets }),
    vlan: factory.vlanState({ items: [vlan] }),
  });

  renderWithProviders(<FabricVLANsTable fabric={fabric} />, { state });

  const dataRows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole(
    "row"
  );

  const firstRowCells = within(dataRows[0]).getAllByRole("cell");
  const secondRowCells = within(dataRows[1]).getAllByRole("cell");

  // first row for this vlan should contain name and space
  expect(firstRowCells[0]).toHaveTextContent(new RegExp(vlan.name));
  expect(firstRowCells[1]).toHaveTextContent(new RegExp(space.name));
  expect(firstRowCells[2]).toHaveTextContent(new RegExp(subnets[0].name));
  expect(firstRowCells[3]).toHaveTextContent(
    subnets[0].statistics.available_string
  );

  // second row should only contain subnet name and available IPs
  expect(secondRowCells[0].textContent).toBe("");
  expect(secondRowCells[1].textContent).toBe("");
  expect(secondRowCells[2]).toHaveTextContent(new RegExp(subnets[1].name));
  expect(secondRowCells[3]).toHaveTextContent(
    subnets[1].statistics.available_string
  );
});
