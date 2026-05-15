import ComposeForm from "../ComposeForm";

import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  screen,
  renderWithProviders,
  userEvent,
  within,
  expectTooltipOnHover,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  zoneResolvers.listZones.handler(),
  poolsResolvers.listPools.handler()
);

describe("InterfacesTable", () => {
  let initialState: RootState;

  beforeEach(() => {
    const pod = factory.podDetails({ id: 1 });

    initialState = factory.rootState({
      domain: factory.domainState({
        loaded: true,
      }),
      fabric: factory.fabricState({
        loaded: true,
      }),
      general: factory.generalState({
        powerTypes: factory.powerTypesState({
          data: [factory.powerType()],
          loaded: true,
        }),
      }),
      pod: factory.podState({
        items: [pod],
        loaded: true,
        statuses: { [pod.id]: factory.podStatus() },
      }),
      space: factory.spaceState({
        loaded: true,
      }),
      subnet: factory.subnetState({
        loaded: true,
      }),
      vlan: factory.vlanState({
        loaded: true,
      }),
    });
  });

  it("disables add interface button with tooltip if KVM has no available subnets", async () => {
    const pod = factory.podDetails({
      attached_vlans: [],
      boot_vlans: [],
      id: 1,
    });
    const state = { ...initialState };
    state.pod.items = [pod];

    renderWithProviders(<ComposeForm hostId={pod.id} />, {
      state,
      initialEntries: [urls.kvm.lxd.single.index({ id: pod.id })],
    });
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });

    await waitFor(() => screen.getByRole("button", { name: /define/i }));
    const button = screen.getByRole("button", { name: /define/i });
    expect(button).toBeAriaDisabled();

    await expectTooltipOnHover(
      button,
      "There are no available networks seen by this KVM host."
    );
  });

  it("disables add interface button with tooltip if KVM host has no PXE-enabled networks", async () => {
    const fabric = factory.fabric();
    const vlan = factory.vlan({ fabric: fabric.id });
    const subnet = factory.subnet({ vlan: vlan.id });
    const pod = factory.podDetails({
      attached_vlans: [vlan.id],
      boot_vlans: [],
      id: 1,
    });
    const state = { ...initialState };
    state.fabric.items = [fabric];
    state.pod.items = [pod];
    state.subnet.items = [subnet];
    state.vlan.items = [vlan];
    renderWithProviders(<ComposeForm hostId={pod.id} />, {
      state,
      initialEntries: [urls.kvm.lxd.single.index({ id: pod.id })],
    });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /define/i })
      ).toBeInTheDocument();
    });
    const button = screen.getByRole("button", { name: /define/i });
    expect(button).toBeAriaDisabled();
    await expectTooltipOnHover(
      button,
      "There are no PXE-enabled networks seen by this KVM host."
    );
  });

  it("disables add interface button if pod is composing a machine", async () => {
    const pod = factory.podDetails({
      attached_vlans: [1],
      boot_vlans: [1],
      id: 1,
    });
    const subnet = factory.subnet({ vlan: 1 });
    const state = { ...initialState };
    state.pod.items = [pod];
    state.pod.statuses = { [pod.id]: factory.podStatus({ composing: true }) };
    state.subnet.items = [subnet];

    renderWithProviders(<ComposeForm hostId={pod.id} />, {
      state,
      initialEntries: [urls.kvm.lxd.single.index({ id: pod.id })],
    });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /define/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("button", { name: /define/i })
    ).toBeAriaDisabled();
  });

  it("can add and remove interfaces if KVM has PXE-enabled subnets", async () => {
    const pod = factory.podDetails({
      attached_vlans: [1],
      boot_vlans: [1],
      id: 1,
    });
    const subnet = factory.subnet({ vlan: 1 });
    const state = { ...initialState };
    state.pod.items = [pod];
    state.subnet.items = [subnet];

    renderWithProviders(<ComposeForm hostId={pod.id} />, {
      state,
      initialEntries: [urls.kvm.lxd.single.index({ id: pod.id })],
    });
    await waitFor(() => {
      expect(screen.getByTestId("undefined-interface")).toBeInTheDocument();
    });
    // Undefined interface row displays by default
    expect(screen.getByTestId("undefined-interface")).toBeInTheDocument();
    expect(screen.queryByTestId("interface")).not.toBeInTheDocument();

    // Click "Define" button - table row should change to a defined interface
    await userEvent.click(screen.getByRole("button", { name: /Define/i }));
    expect(screen.queryByTestId("undefined-interface")).not.toBeInTheDocument();
    expect(screen.getByTestId("interface")).toBeInTheDocument();

    // Click "Add interface" - another defined interface should be added
    await userEvent.click(
      screen.getByRole("button", { name: /Add interface/i })
    );
    expect(screen.getAllByTestId("interface")).toHaveLength(2);

    // Click delete button - a defined interface should be removed
    await userEvent.click(
      screen.getAllByRole("button", { name: /Delete/i })[0]
    );
    expect(screen.getAllByTestId("interface")).toHaveLength(1);
  });

  it("correctly displays fabric, vlan and PXE details of selected subnet", async () => {
    const fabric = factory.fabric();
    const vlan = factory.vlan({ fabric: fabric.id });
    const subnet = factory.subnet({ vlan: vlan.id });
    const pod = factory.podDetails({
      attached_vlans: [vlan.id],
      boot_vlans: [vlan.id],
      id: 1,
    });
    const state = { ...initialState };
    state.fabric.items = [fabric];
    state.pod.items = [pod];
    state.subnet.items = [subnet];
    state.vlan.items = [vlan];
    renderWithProviders(<ComposeForm hostId={pod.id} />, {
      state,
      initialEntries: [urls.kvm.lxd.single.index({ id: pod.id })],
    });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Define/i })
      ).toBeInTheDocument();
    });
    // Click "Define" button to open interfaces table.
    await userEvent.click(screen.getByRole("button", { name: /Define/i }));
    // Open the menu:
    await userEvent.click(screen.getByRole("button", { name: subnet.name }));
    // Choose the subnet in state from the dropdown
    // Fabric and VLAN nams should display, PXE should be true
    await userEvent.click(
      within(screen.getByLabelText("submenu")).getByRole("button")
    );
    expect(screen.getByText(fabric.name)).toHaveAccessibleName("Fabric");
    expect(screen.getByText(vlan.name)).toHaveAccessibleName("VLAN");
    expect(screen.getByText("PXE"));
    expect(screen.getByLabelText("success"));
  });

  it("preselects the first PXE network if there is one available", async () => {
    const fabric = factory.fabric({ name: "pxe-fabric" });
    const nonBootVlan = factory.vlan({ fabric: fabric.id });
    const bootVlan = factory.vlan({ fabric: fabric.id, name: "pxe-vlan" });
    const nonBootSubnet = factory.subnet({ vlan: nonBootVlan.id });
    const bootSubnet = factory.subnet({
      name: "pxe-subnet",
      vlan: bootVlan.id,
    });
    const pod = factory.podDetails({
      attached_vlans: [nonBootVlan.id, bootVlan.id],
      boot_vlans: [bootVlan.id],
      id: 1,
    });
    const state = { ...initialState };
    state.fabric.items = [fabric];
    state.pod.items = [pod];
    state.subnet.items = [nonBootSubnet, bootSubnet];
    state.vlan.items = [nonBootVlan, bootVlan];
    renderWithProviders(<ComposeForm hostId={pod.id} />, {
      state,
      initialEntries: [urls.kvm.lxd.single.index({ id: pod.id })],
    });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Define/i })
      ).toBeInTheDocument();
    });
    // Click "Define" button to open interfaces table.
    // It should be prepopulated with the first available PXE network details.
    await userEvent.click(screen.getByRole("button", { name: /Define/i }));
    expect(
      screen.getByRole("button", { name: /pxe-subnet/i })
    ).toHaveAccessibleDescription("Subnet");
    expect(screen.getByText("pxe-fabric")).toHaveAccessibleName("Fabric");
    expect(screen.getByText("pxe-vlan")).toHaveAccessibleName("VLAN");
    expect(screen.getByText("PXE"));
    expect(screen.getByLabelText("success"));
  });
});
