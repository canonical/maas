import IPColumn from "./IPColumn";

import { HardwareType } from "@/app/base/enum";
import type { RootState } from "@/app/store/root/types";
import {
  ScriptResultStatus,
  ScriptResultType,
} from "@/app/store/scriptresult/types";
import { NetworkLinkMode } from "@/app/store/types/enum";
import type { VLAN } from "@/app/store/vlan/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("IPColumn", () => {
  let state: RootState;
  let vlan: VLAN;

  beforeEach(() => {
    const fabric = factory.fabric({ name: "fabric-name" });
    vlan = factory.vlan({ fabric: fabric.id, vid: 2, name: "vlan-name" });
    state = factory.rootState({
      fabric: factory.fabricState({
        items: [fabric],
      }),
      vlan: factory.vlanState({
        items: [vlan],
      }),
    });
  });

  it("can display a discovered ip address", () => {
    const discovered = factory.networkDiscoveredIP({ ip_address: "1.2.3.99" });
    const links = [factory.networkLink()];
    const nic = factory.machineInterface({
      discovered: [discovered],
      links,
      vlan_id: vlan.id,
    });
    const machine = factory.machineDetails({
      interfaces: [nic],
      system_id: "abc123",
    });
    state.machine.items = [machine];
    renderWithProviders(<IPColumn link={links[0]} nic={nic} node={machine} />, {
      state,
    });
    expect(screen.getByText(discovered.ip_address)).toBeInTheDocument();
  });

  it("can display an ip address from a link", () => {
    const ip = "1.2.3.99";
    const link = factory.networkLink({
      ip_address: ip,
    });
    const nic = factory.machineInterface({
      discovered: [],
      links: [link],
      vlan_id: vlan.id,
    });
    const machine = factory.machineDetails({
      interfaces: [nic],
      system_id: "abc123",
    });
    state.machine.items = [machine];
    renderWithProviders(<IPColumn link={link} nic={nic} node={machine} />, {
      state,
    });
    expect(screen.getByText(ip)).toBeInTheDocument();
  });

  it("displays as unconfigured when there is no link", () => {
    const nic = factory.machineInterface({
      discovered: [],
      links: [],
      vlan_id: vlan.id,
    });
    const machine = factory.machineDetails({
      interfaces: [nic],
      system_id: "abc123",
    });
    state.machine.items = [machine];
    renderWithProviders(<IPColumn nic={nic} node={machine} />, { state });
    expect(screen.getByText("Unconfigured")).toBeInTheDocument();
  });

  it("can display the link mode", () => {
    const links = [
      factory.networkLink({
        mode: NetworkLinkMode.AUTO,
      }),
    ];
    const nic = factory.machineInterface({
      discovered: [],
      links,
      vlan_id: vlan.id,
    });
    const machine = factory.machineDetails({
      interfaces: [nic],
      system_id: "abc123",
    });
    state.machine.items = [machine];
    renderWithProviders(<IPColumn link={links[0]} nic={nic} node={machine} />, {
      state,
    });
    expect(screen.getByText("Automatic")).toBeInTheDocument();
  });

  it("can display the failed network status for multiple tests", () => {
    const links = [factory.networkLink()];
    const nic = factory.machineInterface({
      discovered: [],
      links,
      vlan_id: vlan.id,
    });
    const machine = factory.machineDetails({
      interfaces: [nic],
      system_id: "abc123",
    });
    state.machine.items = [machine];
    state.scriptresult = factory.scriptResultState({
      items: [
        factory.scriptResult({
          id: 1,
          hardware_type: HardwareType.Network,
          interface: nic,
          result_type: ScriptResultType.TESTING,
          status: ScriptResultStatus.FAILED,
        }),
        factory.scriptResult({
          id: 2,
          hardware_type: HardwareType.Network,
          interface: nic,
          result_type: ScriptResultType.TESTING,
          status: ScriptResultStatus.FAILED,
        }),
      ],
    });
    state.nodescriptresult = factory.nodeScriptResultState({
      items: { abc123: [1, 2] },
    });
    renderWithProviders(<IPColumn link={links[0]} nic={nic} node={machine} />, {
      state,
    });
    expect(screen.getByText("2 failed tests")).toBeInTheDocument();
  });

  it("can display the failed network status for one test", () => {
    const links = [factory.networkLink()];
    const nic = factory.machineInterface({
      discovered: [],
      links,
      vlan_id: vlan.id,
    });
    const machine = factory.machineDetails({
      interfaces: [nic],
      system_id: "abc123",
    });
    state.machine.items = [machine];
    state.scriptresult = factory.scriptResultState({
      items: [
        factory.scriptResult({
          id: 1,
          hardware_type: HardwareType.Network,
          interface: nic,
          name: "nic test",
          result_type: ScriptResultType.TESTING,
          status: ScriptResultStatus.FAILED,
        }),
      ],
    });
    state.nodescriptresult = factory.nodeScriptResultState({
      items: { abc123: [1, 2] },
    });
    renderWithProviders(<IPColumn link={links[0]} nic={nic} node={machine} />, {
      state,
    });
    expect(screen.getByText("nic test failed")).toBeInTheDocument();
  });

  it("can not display the failed network status", () => {
    const nic = factory.machineInterface({
      discovered: [],
      links: [factory.networkLink()],
      vlan_id: vlan.id,
    });
    const machine = factory.machineDetails({
      interfaces: [],
      system_id: "abc123",
    });
    state.machine.items = [machine];
    renderWithProviders(<IPColumn nic={nic} node={machine} />, { state });
    expect(screen.queryByText("failed")).not.toBeInTheDocument();
  });
});
