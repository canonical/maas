import MapSubnet from "./MapSubnet";

import { subnetActions } from "@/app/store/subnet";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

describe("MapSubnet", () => {
  it("shows a spinner while subnet is loading", () => {
    const state = factory.rootState({
      subnet: factory.subnetState({ items: [] }),
    });
    renderWithProviders(<MapSubnet subnetId={1} />, { state });

    expect(screen.getByTestId("loading-subnet")).toBeInTheDocument();
  });

  it("shows an error if the subnet is IPv6", () => {
    const subnet = factory.subnet({ version: 6 });
    const state = factory.rootState({
      subnet: factory.subnetState({ items: [subnet] }),
    });
    renderWithProviders(<MapSubnet subnetId={subnet.id} />, { state });

    expect(
      screen.getByText("Only IPv4 subnets can be scanned.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Map subnet" })).toBeDisabled();
  });

  it("can map an IPv4 subnet", async () => {
    const subnet = factory.subnet({ version: 4 });
    const state = factory.rootState({
      subnet: factory.subnetState({ items: [subnet] }),
    });
    const { store } = renderWithProviders(<MapSubnet subnetId={subnet.id} />, {
      state,
    });

    await userEvent.click(screen.getByRole("button", { name: "Map subnet" }));

    await waitFor(() => {
      const expectedAction = subnetActions.scan(subnet.id);
      const actualActions = store.getActions();

      expect(
        actualActions.find((action) => action.type === expectedAction.type)
      ).toStrictEqual(expectedAction);
    });
  });
});
