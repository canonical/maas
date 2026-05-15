import DeleteSubnet from "./DeleteSubnet";

import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import { vlanActions } from "@/app/store/vlan";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

describe("DeleteSubnet", () => {
  const subnet = factory.subnetDetails({
    id: 1,
    vlan: 1,
  });
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      subnet: factory.subnetState({
        items: [subnet],
        loading: false,
        loaded: true,
      }),
      vlan: factory.vlanState({
        items: [
          factory.vlan({
            id: 1,
            dhcp_on: true,
          }),
        ],
        loading: false,
        loaded: true,
      }),
    });
  });

  it("displays a correct error message for a subnet with IPs obtained through DHCP", async () => {
    state.subnet.items = [
      factory.subnetDetails({
        id: subnet.id,
        ip_addresses: [factory.subnetIP()],
        vlan: 1,
      }),
    ];
    renderWithProviders(<DeleteSubnet subnet={state.subnet.items[0]} />, {
      state,
      initialEntries: [urls.networks.subnet.index({ id: subnet.id })],
    });
    const deleteSubnetSection = screen.getByRole("form", {
      name: /Delete subnet/,
    });

    await waitFor(() => {
      expect(
        within(deleteSubnetSection).getByText(
          /This subnet cannot be deleted as there are nodes that have an IP address obtained through DHCP services on this subnet./
        )
      ).toBeInTheDocument();
    });
  });

  it("displays a message if DHCP is disabled on the VLAN", () => {
    state.vlan.items[0].dhcp_on = false;
    renderWithProviders(<DeleteSubnet subnet={subnet} />, {
      state,
      initialEntries: [urls.networks.subnet.index({ id: subnet.id })],
    });
    const deleteSubnetSection = screen.getByRole("form", {
      name: /Delete subnet/,
    });

    expect(
      within(deleteSubnetSection).getByText(
        /Beware IP addresses on devices on this subnet might not be retained/
      )
    ).toBeInTheDocument();
  });

  it("does not display a message if DHCP is enabled on the VLAN", () => {
    state.vlan.items[0].dhcp_on = true;
    renderWithProviders(<DeleteSubnet subnet={subnet} />, {
      state,
      initialEntries: [urls.networks.subnet.index({ id: subnet.id })],
    });
    const deleteSubnetSection = screen.getByRole("form", {
      name: /Delete subnet/,
    });

    expect(
      within(deleteSubnetSection).queryByText(
        /Beware IP addresses on devices on this subnet might not be retained/
      )
    ).not.toBeInTheDocument();
  });

  it("dispatches an action to load vlans and subnets if not loaded", () => {
    state.vlan.loaded = false;
    state.subnet.loaded = false;
    const { store } = renderWithProviders(<DeleteSubnet subnet={subnet} />, {
      state,
      initialEntries: [urls.networks.subnet.index({ id: subnet.id })],
    });
    const expectedActions = [vlanActions.fetch(), subnetActions.fetch()];
    const actualActions = store.getActions();
    expectedActions.forEach((expectedAction) => {
      expect(
        actualActions.find(
          (actualAction) => actualAction.type === expectedAction.type
        )
      ).toStrictEqual(expectedAction);
    });
  });

  it("dispatches a delete action on submit", async () => {
    state.vlan.items[0].dhcp_on = false;
    const { store } = renderWithProviders(<DeleteSubnet subnet={subnet} />, {
      state,
      initialEntries: [urls.networks.subnet.index({ id: subnet.id })],
    });

    expect(
      screen.getByText(/Are you sure you want to delete this subnet?/)
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Delete/i }));

    const expectedAction = subnetActions.delete(subnet.id);
    const actualAction = store
      .getActions()
      .find((actualAction) => actualAction.type === expectedAction.type);
    expect(actualAction).toStrictEqual(expectedAction);
  });

  it("redirects on save", async () => {
    state.vlan.items[0].dhcp_on = false;

    renderWithProviders(<DeleteSubnet subnet={subnet} />, {
      state,
      initialEntries: [urls.networks.subnet.index({ id: subnet.id })],
    });

    state.subnet.saved = true;

    const { router } = renderWithProviders(<DeleteSubnet subnet={subnet} />, {
      state,
      initialEntries: [urls.networks.subnet.index({ id: subnet.id })],
    });

    await waitFor(() => {
      expect(router.state.location.pathname).toEqual(urls.networks.index);
    });
  });
});
