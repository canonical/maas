import KVMConfigurationCard from "../KVMConfigurationCard";

import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  waitFor,
  within,
  userEvent,
} from "@/testing/utils";

setupMockServer(
  poolsResolvers.listPools.handler(),
  zoneResolvers.listZones.handler()
);

describe("KVMConfigurationCardFields", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      pod: factory.podState({ items: [], loaded: true }),
    });
  });

  it("correctly sets initial values for virsh pods", async () => {
    const pod = factory.podDetails({
      id: 1,
      power_parameters: factory.podPowerParameters({
        power_address: "abc123",
        power_pass: "maxpower",
      }),
      pool: 1,
      zone: 1,
      type: PodType.VIRSH,
    });
    state.pod.items = [pod];
    renderWithProviders(<KVMConfigurationCard pod={pod} />, {
      state,
    });
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });

    expect(screen.getByRole("textbox", { name: "KVM host type" })).toHaveValue(
      "Virsh"
    );
    await waitFor(() => {
      expect(
        (
          within(screen.getByRole("combobox", { name: "Zone" })).getByRole(
            "option",
            { name: "zone-1" }
          ) as HTMLOptionElement
        ).selected
      ).toBe(true);
    });
    expect(
      (
        within(
          screen.getByRole("combobox", { name: "Resource pool" })
        ).getByRole("option", { name: "swimming" }) as HTMLOptionElement
      ).selected
    ).toBe(true);
    expect(
      screen.getByRole("spinbutton", { name: "CPU overcommit" })
    ).toHaveValue(pod.cpu_over_commit_ratio);
    expect(
      screen.getByRole("spinbutton", { name: "Memory overcommit" })
    ).toHaveValue(pod.memory_over_commit_ratio);
  });

  it("correctly sets initial values for lxd pods", async () => {
    const pod = factory.podDetails({
      id: 1,
      power_parameters: factory.podPowerParameters({
        power_address: "abc123",
      }),
      pool: 1,
      zone: 1,
      type: PodType.LXD,
    });
    state.pod.items = [pod];
    renderWithProviders(<KVMConfigurationCard pod={pod} />, {
      state,
    });
    await waitFor(() => {
      expect(
        screen.getByRole("combobox", { name: "Zone" })
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("textbox", { name: "KVM host type" })).toHaveValue(
      "LXD"
    );
    await userEvent.click(screen.getByRole("combobox", { name: "Zone" }));
    expect(
      (
        within(screen.getByRole("combobox", { name: "Zone" })).getByRole(
          "option",
          { name: "zone-1" }
        ) as HTMLOptionElement
      ).selected
    ).toBe(true);
    expect(
      (
        within(
          screen.getByRole("combobox", { name: "Resource pool" })
        ).getByRole("option", { name: "swimming" }) as HTMLOptionElement
      ).selected
    ).toBe(true);
    expect(
      screen.getByRole("spinbutton", { name: "CPU overcommit" })
    ).toHaveValue(pod.cpu_over_commit_ratio);
    expect(
      screen.getByRole("spinbutton", { name: "Memory overcommit" })
    ).toHaveValue(pod.memory_over_commit_ratio);
  });

  it("can disable the zone field", () => {
    const pod = factory.podDetails({
      id: 1,
      power_parameters: factory.podPowerParameters({
        power_address: "abc123",
      }),
      type: PodType.LXD,
    });
    state.pod.items = [pod];
    renderWithProviders(<KVMConfigurationCard pod={pod} zoneDisabled />, {
      state,
    });
    expect(screen.getByRole("combobox", { name: "Zone" })).toBeDisabled();
  });
});
