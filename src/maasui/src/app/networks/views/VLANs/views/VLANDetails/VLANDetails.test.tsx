import { Route, Routes } from "react-router";

import VLANDetails from "./VLANDetails";

import urls from "@/app/base/urls";
import { vlanActions } from "@/app/store/vlan";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("VLANDetails", () => {
  it("dispatches actions to fetch necessary data and set vlan as active on mount", async () => {
    const state = factory.rootState({
      vlan: factory.vlanState({
        items: [factory.vlan({ id: 1, space: 3 })],
      }),
    });
    const { store } = renderWithProviders(
      <Routes>
        <Route
          element={<VLANDetails />}
          path={urls.networks.vlan.index(null)}
        />
      </Routes>,
      {
        initialEntries: [urls.networks.vlan.index({ id: 1 })],
        state,
      }
    );

    const expectedActions = [vlanActions.get(1), vlanActions.setActive(1)];
    const actualActions = store.getActions();
    expectedActions.forEach((expectedAction) => {
      expect(
        actualActions.find(
          (actualAction) => actualAction.type === expectedAction.type
        )
      ).toStrictEqual(expectedAction);
    });
  });

  it("dispatches actions to unset active vlan and clean up on unmount", () => {
    const state = factory.rootState();
    const { result, store } = renderWithProviders(
      <Routes>
        <Route
          element={<VLANDetails />}
          path={urls.networks.vlan.index(null)}
        />
      </Routes>,
      { state, initialEntries: [urls.networks.vlan.index({ id: 1 })] }
    );

    result.unmount();

    const expectedActions = [
      vlanActions.setActive(null),
      vlanActions.cleanup(),
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

  it("displays a message if the vlan does not exist", () => {
    const state = factory.rootState({
      vlan: factory.vlanState({
        items: [],
        loading: false,
      }),
    });
    renderWithProviders(
      <Routes>
        <Route
          element={<VLANDetails />}
          path={urls.networks.vlan.index(null)}
        />
      </Routes>,
      { state, initialEntries: [urls.networks.vlan.index({ id: 1 })] }
    );

    expect(screen.getByText("VLAN not found")).toBeInTheDocument();
  });
});
