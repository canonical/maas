import { AddStaticRouteFormLabels } from "./AddStaticRouteForm/AddStaticRouteForm";
import StaticRoutes from "./StaticRoutes";

import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(authResolvers.getCurrentUser.handler());

it("renders for a subnet", () => {
  const subnet = factory.subnet({ id: 1 });
  const state = factory.rootState({
    staticroute: factory.staticRouteState({
      items: [
        factory.staticRoute({
          gateway_ip: "11.1.1.1",
          source: 1,
        }),
        factory.staticRoute({
          gateway_ip: "11.1.1.2",
          source: 1,
        }),
      ],
    }),
    subnet: factory.subnetState({
      items: [subnet],
    }),
  });

  renderWithProviders(<StaticRoutes subnetId={subnet.id} />, { state });

  expect(screen.getByRole("row", { name: /^11.1.1.1/ }));
  expect(screen.getByRole("row", { name: /^11.1.1.2/ }));
});

it("has a button to open the static route form", async () => {
  const subnet = factory.subnet({ id: 1 });
  const state = factory.rootState({
    staticroute: factory.staticRouteState({
      items: [],
    }),
    subnet: factory.subnetState({
      items: [subnet, factory.subnet({ id: 2 })],
    }),
  });

  renderWithProviders(<StaticRoutes subnetId={subnet.id} />, { state });

  await waitFor(() => {
    expect(authResolvers.getCurrentUser.resolved).toBe(true);
  });
  await waitFor(() => {
    expect(
      screen.getByRole("button", {
        name: AddStaticRouteFormLabels.AddStaticRoute,
      })
    ).toBeInTheDocument();
  });
});

it("has a button to open the edit static route form", async () => {
  const subnet = factory.subnet({ id: 1 });
  const state = factory.rootState({
    staticroute: factory.staticRouteState({
      items: [
        factory.staticRoute({
          gateway_ip: "11.1.1.1",
          source: 1,
        }),
      ],
    }),
    subnet: factory.subnetState({
      items: [subnet],
    }),
  });

  renderWithProviders(<StaticRoutes subnetId={subnet.id} />, { state });

  expect(
    screen.getByRole("button", {
      name: "Edit",
    })
  ).toBeInTheDocument();
});
