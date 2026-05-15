import EditBootArchitectures from "./EditBootArchitectures";

import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

describe("EditBootArchitectures", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      general: factory.generalState({
        knownBootArchitectures: factory.knownBootArchitecturesState({
          data: [
            factory.knownBootArchitecture({ name: "arch1" }),
            factory.knownBootArchitecture({ name: "arch2" }),
          ],
          loading: false,
        }),
      }),
      subnet: factory.subnetState({
        items: [
          factory.subnet({
            id: 1,
            disabled_boot_architectures: ["arch1"],
          }),
        ],
      }),
    });
  });

  it("shows a spinner while data is loading", () => {
    state.general.knownBootArchitectures.loading = true;
    renderWithProviders(<EditBootArchitectures subnetId={1} />, { state });

    expect(screen.getByTestId("loading-data")).toBeInTheDocument();
  });

  it("initialises form data correctly", () => {
    renderWithProviders(<EditBootArchitectures subnetId={1} />, { state });
    const nameCells = within(screen.getAllByRole("rowgroup")[1])
      .getAllByRole("row")
      .map((row) => within(row).getAllByRole("cell")[0]);

    // First arch is disabled, second arch is not.
    expect(within(nameCells[0]).getByRole("checkbox")).not.toBeChecked();
    expect(within(nameCells[1]).getByRole("checkbox")).toBeChecked();
  });

  it("can update the arches to disable", async () => {
    renderWithProviders(<EditBootArchitectures subnetId={1} />, { state });
    const nameCells = within(screen.getAllByRole("rowgroup")[1])
      .getAllByRole("row")
      .map((row) => within(row).getAllByRole("cell")[0]);

    await userEvent.click(within(nameCells[0]).getByRole("checkbox"));
    await userEvent.click(within(nameCells[1]).getByRole("checkbox"));

    await waitFor(() => {
      expect(within(nameCells[0]).getByRole("checkbox")).toBeChecked();
    });
    expect(within(nameCells[1]).getByRole("checkbox")).not.toBeChecked();
  });

  it("can dispatch an action to update subnet's disabled boot architectures", async () => {
    state.subnet.items = [
      factory.subnet({
        id: 1,
      }),
    ];
    const { store } = renderWithProviders(
      <EditBootArchitectures subnetId={1} />,
      { state }
    );
    const nameCells = within(screen.getAllByRole("rowgroup")[1])
      .getAllByRole("row")
      .map((row) => within(row).getAllByRole("cell")[0]);

    await userEvent.click(within(nameCells[0]).getByRole("checkbox"));
    await userEvent.click(within(nameCells[1]).getByRole("checkbox"));

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    const expectedAction = subnetActions.update({
      id: 1,
      disabled_boot_architectures: "arch1, arch2",
    });

    await waitFor(() => {
      const actualActions = store.getActions();
      expect(
        actualActions.find((action) => action.type === expectedAction.type)
      ).toStrictEqual(expectedAction);
    });
  });
});
