import { Route, Routes } from "react-router";

import SubnetDetails from "./SubnetDetails";

import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import { staticRouteActions } from "@/app/store/staticroute";
import { subnetActions } from "@/app/store/subnet";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, waitFor } from "@/testing/utils";

describe("SubnetDetails", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      subnet: factory.subnetState({
        items: [factory.subnet({ id: 1 })],
      }),
    });
  });

  [
    {
      component: "SubnetSummary",
      path: urls.networks.subnet.summary({ id: 1 }),
      title: "Subnet summary",
    },
    {
      component: "StaticRoutes",
      path: urls.networks.subnet.staticRoutes({ id: 1 }),
      title: "Static routes",
    },
    {
      component: "ReservedRangesTable",
      path: urls.networks.subnet.addressReservation({ id: 1 }),
      title: "Reserved ranges",
    },
    {
      component: "DHCPSnippets",
      path: urls.networks.subnet.dhcpSnippets({ id: 1 }),
      title: "DHCP snippets",
    },
    {
      component: "SubnetUsedIPs",
      path: urls.networks.subnet.usedIpAddresses({ id: 1 }),
      title: "Used IP addresses",
    },
  ].forEach(({ component, path, title }) => {
    it(`Displays ${component} at ${path}`, async () => {
      renderWithProviders(
        <Routes>
          <Route
            element={<SubnetDetails />}
            path={`${urls.networks.subnet.index(null)}/*`}
          />
        </Routes>,
        {
          initialEntries: [path],
          state,
        }
      );

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: title })
        ).toBeInTheDocument();
      });
    });
  });

  it("redirects to summary", () => {
    const { router } = renderWithProviders(
      <Routes>
        <Route
          element={<SubnetDetails />}
          path={`${urls.networks.subnet.index(null)}/*`}
        />
      </Routes>,
      {
        initialEntries: [urls.networks.subnet.index({ id: 1 })],
        state,
      }
    );

    expect(router.state.location.pathname).toBe(
      urls.networks.subnet.summary({ id: 1 })
    );
  });

  it("dispatches actions to fetch necessary data and set subnet as active on mount", () => {
    const { store } = renderWithProviders(
      <Routes>
        <Route
          element={<SubnetDetails />}
          path={`${urls.networks.subnet.index(null)}/*`}
        />
      </Routes>,
      {
        initialEntries: [urls.networks.subnet.index({ id: 1 })],
        state,
      }
    );

    const expectedActions = [
      subnetActions.get(1),
      subnetActions.setActive(1),
      staticRouteActions.fetch(),
    ];
    const actualActions = store.getActions();
    expectedActions.forEach((expectedAction) => {
      expect(
        actualActions.find(
          (actualAction) => actualAction.type === expectedAction.type
        )
      ).toStrictEqual(expectedAction);
    });
  });

  it("dispatches actions to unset active subnet and clean up on unmount", () => {
    const { result, store } = renderWithProviders(
      <Routes>
        <Route
          element={<SubnetDetails />}
          path={`${urls.networks.subnet.index(null)}/*`}
        />
      </Routes>,
      {
        initialEntries: [urls.networks.subnet.index({ id: 1 })],
        state,
      }
    );

    result.unmount();

    const expectedActions = [
      subnetActions.setActive(null),
      subnetActions.cleanup(),
    ];
    const actualActions = store.getActions();
    expectedActions.forEach((expectedAction) => {
      expect(
        actualActions.find(
          (actualAction) =>
            actualAction.type === expectedAction.type &&
            // Check payload to differentiate "set" and "unset" active actions
            actualAction.payload?.params === expectedAction.payload?.params
        )
      ).toStrictEqual(expectedAction);
    });
  });

  it("displays a message if the subnet does not exist", () => {
    state.subnet = factory.subnetState({
      items: [],
      loading: false,
    });
    renderWithProviders(
      <Routes>
        <Route
          element={<SubnetDetails />}
          path={`${urls.networks.subnet.index(null)}/*`}
        />
      </Routes>,
      {
        initialEntries: [urls.networks.subnet.index({ id: 1 })],
        state,
      }
    );

    expect(screen.getByText("Subnet not found")).toBeInTheDocument();
  });

  it("shows a spinner if the subnet has not loaded yet", () => {
    state.subnet = factory.subnetState({
      items: [],
      loading: true,
    });
    renderWithProviders(
      <Routes>
        <Route
          element={<SubnetDetails />}
          path={`${urls.networks.subnet.index(null)}/*`}
        />
      </Routes>,
      {
        initialEntries: [urls.networks.subnet.index({ id: 1 })],
        state,
      }
    );

    expect(
      screen.getByTestId("section-header-title-spinner")
    ).toBeInTheDocument();
  });
});
