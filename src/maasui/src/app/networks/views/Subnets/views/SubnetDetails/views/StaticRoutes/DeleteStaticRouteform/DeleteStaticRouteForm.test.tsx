import DeleteStaticRouteForm from "./DeleteStaticRouteForm";

import { staticRouteActions } from "@/app/store/staticroute";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

const subnet = factory.subnet({ id: 1, cidr: "172.16.1.0/24" });
const destinationSubnet = factory.subnet({ id: 2, cidr: "223.16.1.0/24" });
const staticroute = factory.staticRoute({ id: 1, destination: subnet.id });
const state = factory.rootState({
  staticroute: factory.staticRouteState({
    loaded: true,
    items: [staticroute],
  }),
  subnet: factory.subnetState({
    loaded: true,
    items: [subnet, destinationSubnet],
  }),
});

describe("DeleteStaticRouteForm", () => {
  it("renders", () => {
    renderWithProviders(
      <DeleteStaticRouteForm staticRouteId={staticroute.id} />,
      { state }
    );

    expect(screen.getByRole("form", { name: "Confirm static route deletion" }));
  });

  it("dispatches the correct action to delete a static route", async () => {
    const { store } = renderWithProviders(
      <DeleteStaticRouteForm staticRouteId={staticroute.id} />,
      { state }
    );

    await userEvent.click(screen.getByRole("button", { name: /delete/i }));

    const action = store
      .getActions()
      .find((action) => action.type === staticRouteActions.delete.type);

    expect(action).toStrictEqual(staticRouteActions.delete(staticroute.id));
  });
});
