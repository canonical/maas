import { Route, Routes } from "react-router";

import FabricDetails from "./FabricDetails";

import urls from "@/app/base/urls";
import { fabricActions } from "@/app/store/fabric";
import { subnetActions } from "@/app/store/subnet";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("FabricDetails", () => {
  it("dispatches actions to fetch necessary data and set fabric as active on mount", () => {
    const { store } = renderWithProviders(
      <Routes>
        <Route
          element={<FabricDetails />}
          path={urls.networks.fabric.index(null)}
        />
      </Routes>,
      {
        initialEntries: [urls.networks.fabric.index({ id: 1 })],
      }
    );

    const expectedActions = [
      fabricActions.get(1),
      fabricActions.setActive(1),
      subnetActions.fetch(),
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

  it("displays a message if the fabric does not exist", () => {
    const state = factory.rootState({
      fabric: factory.fabricState({
        items: [],
        loading: false,
      }),
    });
    renderWithProviders(
      <Routes>
        <Route
          element={<FabricDetails />}
          path={urls.networks.fabric.index(null)}
        />
      </Routes>,
      { initialEntries: [urls.networks.fabric.index({ id: 1 })], state }
    );

    expect(screen.getByText("Fabric not found")).toBeInTheDocument();
  });

  it("shows a spinner if the fabric has not loaded yet", () => {
    const state = factory.rootState({
      fabric: factory.fabricState({
        items: [],
        loading: true,
      }),
    });
    renderWithProviders(
      <Routes>
        <Route
          element={<FabricDetails />}
          path={urls.networks.fabric.index(null)}
        />
      </Routes>,
      { initialEntries: [urls.networks.fabric.index({ id: 1 })], state }
    );

    expect(
      screen.getByTestId("section-header-title-spinner")
    ).toBeInTheDocument();
  });
});
