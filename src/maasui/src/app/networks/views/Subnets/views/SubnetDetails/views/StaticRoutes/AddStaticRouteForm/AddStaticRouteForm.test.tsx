import { Labels } from "../StaticRoutes";

import AddStaticRouteForm from "./AddStaticRouteForm";

import { staticRouteActions } from "@/app/store/staticroute";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  within,
  renderWithProviders,
} from "@/testing/utils";

it("dispatches a correct action on add static route form submit", async () => {
  const subnet = factory.subnet({ id: 1, cidr: "172.16.1.0/24" });
  const destinationSubnet = factory.subnet({ id: 2, cidr: "223.16.1.0/24" });
  const state = factory.rootState({
    staticroute: factory.staticRouteState({
      loaded: true,
      items: [],
    }),
    subnet: factory.subnetState({
      loaded: true,
      items: [subnet, destinationSubnet],
    }),
  });

  const { store } = renderWithProviders(
    <AddStaticRouteForm subnetId={subnet.id} />,
    { state }
  );

  await waitFor(() => {
    expect(
      screen.getByRole("form", { name: "Add static route" })
    ).toBeInTheDocument();
  });

  const addStaticRouteForm = screen.getByRole("form", {
    name: "Add static route",
  });

  const gatewayIp = "11.1.1.2";
  await userEvent.type(
    within(addStaticRouteForm).getByLabelText(Labels.GatewayIp),
    gatewayIp
  );
  await userEvent.clear(
    within(addStaticRouteForm).getByLabelText(Labels.Metric)
  );
  await userEvent.type(
    within(addStaticRouteForm).getByLabelText(Labels.Metric),
    "1"
  );
  await userEvent.selectOptions(
    within(addStaticRouteForm).getByLabelText(Labels.Destination),
    `${destinationSubnet.id}`
  );
  await userEvent.click(
    within(addStaticRouteForm).getByRole("button", {
      name: "Save",
    })
  );

  const expectedActions = [
    staticRouteActions.create({
      source: subnet.id,
      gateway_ip: gatewayIp,
      destination: destinationSubnet.id,
      metric: 1,
    }),
  ];
  const actualActions = store.getActions();
  await waitFor(() => {
    expect(
      actualActions.filter(
        (action) => action.type === staticRouteActions.create.type
      )
    ).toStrictEqual(expectedActions);
  });
});
