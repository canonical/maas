import DeleteDHCPLease from "./DeleteDHCPLease";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  getTestState,
  renderWithProviders,
  screen,
  userEvent,
} from "@/testing/utils";

let state: RootState;

describe("DeleteDHCPLease", () => {
  beforeEach(() => {
    state = getTestState();
    state.subnet = factory.subnetState({
      loading: false,
      loaded: true,
      items: [factory.subnet({ id: 1, cidr: "10.0.0.0/24" })],
    });
    state.reservedip = factory.reservedIpState({
      loading: false,
      loaded: true,
      items: [factory.reservedIp({ id: 1, ip: "10.0.0.2" })],
    });
  });

  it("renders a delete confirmation form", () => {
    renderWithProviders(<DeleteDHCPLease reservedIpId={1} />, { state });
    expect(
      screen.getByRole("form", { name: "Delete static IP" })
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        `Are you sure you want to delete ${state.reservedip.items[0].ip}? This action is permanent and cannot be undone.`
      )
    ).toBeInTheDocument();
  });

  it("dispatches an action to delete a reserved IP", async () => {
    const { store } = renderWithProviders(
      <DeleteDHCPLease reservedIpId={1} />,
      {
        state,
      }
    );

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(
      store.getActions().find((action) => action.type === "reservedip/delete")
    ).toEqual({
      meta: {
        method: "delete",
        model: "reservedip",
      },
      payload: {
        params: {
          id: 1,
          ip: state.reservedip.items[0].ip,
        },
      },
      type: "reservedip/delete",
    });
  });
});
