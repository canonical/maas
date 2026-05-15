import DeleteFabric from "./DeleteFabric";

import { fabricActions } from "@/app/store/fabric";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

it("does not allow deletion if the fabric is the default fabric", () => {
  const fabric = factory.fabric({ id: 0 });
  const state = factory.rootState({
    fabric: factory.fabricState({
      items: [fabric],
    }),
  });

  renderWithProviders(<DeleteFabric id={fabric.id} />, { state });

  expect(
    screen.getByText(
      "This fabric cannot be deleted because it is the default fabric for this MAAS."
    )
  ).toBeInTheDocument();
});

it("does not allow deletion if the fabric has subnets attached", () => {
  const subnet = factory.subnet({ vlan: 101 });
  const fabric = factory.fabric({ id: 1, vlan_ids: [subnet.vlan] });
  const state = factory.rootState({
    fabric: factory.fabricState({
      items: [fabric],
    }),
    subnet: factory.subnetState({
      items: [subnet],
    }),
  });

  renderWithProviders(<DeleteFabric id={fabric.id} />, { state });

  expect(
    screen.getByText(
      "This fabric cannot be deleted because it has subnets attached. Remove all subnets from the VLANs on this fabric to allow deletion."
    )
  ).toBeInTheDocument();
});

it(`displays a delete confirmation if the fabric is not the default and has no
    subnets attached`, () => {
  const fabric = factory.fabric({ id: 1 });
  const state = factory.rootState({
    fabric: factory.fabricState({ items: [fabric] }),
  });

  renderWithProviders(<DeleteFabric id={fabric.id} />, { state });

  expect(
    screen.getByText("Are you sure you want to delete this fabric?")
  ).toBeInTheDocument();
});

it("deletes the fabric when confirmed", async () => {
  const fabric = factory.fabric({ id: 1 });
  const state = factory.rootState({
    fabric: factory.fabricState({ items: [fabric] }),
  });

  const { store } = renderWithProviders(<DeleteFabric id={fabric.id} />, {
    state,
  });

  await userEvent.click(screen.getByRole("button", { name: "Delete fabric" }));

  const expectedActions = [fabricActions.delete(fabric.id)];
  const actualActions = store.getActions();
  await waitFor(() => {
    expectedActions.forEach((expectedAction) => {
      expect(
        actualActions.find(
          (actualAction) => actualAction.type === expectedAction.type
        )
      ).toStrictEqual(expectedAction);
    });
  });
});
