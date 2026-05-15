import FabricSummary from "./FabricSummary";

import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  within,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

it("renders correct details", () => {
  const controller = factory.controller({
    hostname: "bolla",
    system_id: "1234",
    domain: factory.modelRef({ name: "maas" }),
  });
  const state = factory.rootState({
    vlan: factory.vlanState({
      loaded: true,
      items: [factory.vlan({ fabric: 2, rack_sids: ["system-id"] })],
    }),
    controller: factory.controllerState({
      loaded: true,
      items: [controller],
    }),
  });
  const fabric = factory.fabric({ id: 1, name: "test-fabric" });

  renderWithProviders(<FabricSummary fabric={fabric} />, {
    state,
  });

  expect(
    screen.getByRole("heading", { name: "Fabric summary" })
  ).toBeInTheDocument();
  expect(screen.getByText("test-fabric")).toBeInTheDocument();
});

it("can open and close the Edit fabric summary form", async () => {
  const fabric = factory.fabric({
    name: "fabric-1",
    description: "fabric-1 description",
  });
  const state = factory.rootState({
    fabric: factory.fabricState({
      items: [fabric],
      loading: false,
    }),
  });
  renderWithProviders(<FabricSummary fabric={fabric} />, {
    state,
  });
  const fabricSummary = screen.getByRole("region", { name: "Fabric summary" });
  await userEvent.click(
    within(fabricSummary).getAllByRole("button", { name: "Edit" })[0]
  );
  await waitFor(() => {
    expect(
      screen.getByRole("form", { name: "Edit fabric summary" })
    ).toBeInTheDocument();
  });

  await userEvent.click(
    within(fabricSummary).getByRole("button", { name: "Cancel" })
  );
  await waitFor(() => {
    expect(
      screen.queryByRole("form", { name: "Edit fabric summary" })
    ).not.toBeInTheDocument();
  });
});
