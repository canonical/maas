import VLANSummary from "./VLANSummary";

import urls from "@/app/base/urls";
import { EditVLAN } from "@/app/networks/views/VLANs/components";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

setupMockServer(authResolvers.getCurrentUser.handler());
const { mockOpen } = await mockSidePanel();

describe("VLANSummary", () => {
  const fabric = factory.fabric({ id: 1, name: "fabric-1" });
  const space = factory.space({ id: 22, name: "outer" });
  const controller = factory.controller({
    domain: factory.modelRef({ name: "domain" }),
    hostname: "controller-abc",
    system_id: "abc123",
  });
  const vlan = factory.vlan({
    description: "I'm a little VLAN",
    fabric: fabric.id,
    mtu: 5432,
    name: "vlan-333",
    primary_rack: controller.system_id,
    space: space.id,
    vid: 1010,
  });
  const state = factory.rootState({
    controller: factory.controllerState({ items: [controller] }),
    fabric: factory.fabricState({ items: [fabric] }),
    space: factory.spaceState({ items: [space] }),
    vlan: factory.vlanState({ items: [vlan] }),
  });

  it("renders correct details", () => {
    renderWithProviders(<VLANSummary id={vlan.id} />, { state });
    const vlanSummary = screen.getByRole("region", { name: "VLAN summary" });
    expect(
      within(vlanSummary).getByRole("link", { name: space.name })
    ).toHaveAttribute("href", urls.networks.space.index({ id: space.id }));
    expect(
      within(vlanSummary).getByRole("link", { name: fabric.name })
    ).toHaveAttribute("href", urls.networks.fabric.index({ id: fabric.id }));
    expect(
      within(vlanSummary).getByRole("link", { name: /controller-abc/i })
    ).toHaveAttribute(
      "href",
      urls.controllers.controller.index({ id: controller.system_id })
    );
  });

  it("can trigger the edit form side panel", async () => {
    renderWithProviders(<VLANSummary id={vlan.id} />, { state });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(mockOpen).toHaveBeenCalledWith({
      component: EditVLAN,
      title: "Edit VLAN",
      props: { id: vlan.id },
    });
  });
});
