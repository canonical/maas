import KVMConfigurationCard from "./KVMConfigurationCard";

import { podActions } from "@/app/store/pod";
import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  userEvent,
  fireEvent,
  screen,
  waitFor,
  renderWithProviders,
  setupMockServer,
} from "@/testing/utils";

let state: RootState;
setupMockServer(
  poolsResolvers.listPools.handler(),
  zoneResolvers.listZones.handler()
);

describe("KVMConfigurationCard", () => {
  beforeEach(() => {
    state = factory.rootState({
      pod: factory.podState({
        items: [factory.podDetails({ id: 1, name: "pod1" })],
        loaded: true,
      }),
    });
  });

  it("can handle updating a lxd KVM", async () => {
    const pod = factory.podDetails({
      id: 1,
      tags: ["tag1", "tag2"],
      type: PodType.LXD,
    });
    const { store } = renderWithProviders(<KVMConfigurationCard pod={pod} />, {
      state,
    });
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });

    await waitFor(() => screen.getByRole("combobox", { name: "Zone" }));

    await userEvent.click(screen.getByRole("combobox", { name: "Zone" }));

    expect(screen.getByText("zone-3")).toBeInTheDocument();

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Zone" }),
      "3"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Resource pool" }),
      "2"
    );
    fireEvent.change(screen.getByRole("slider", { name: "CPU overcommit" }), {
      target: { value: "5" },
    });
    fireEvent.change(
      screen.getByRole("slider", { name: "Memory overcommit" }),
      {
        target: { value: "7" },
      }
    );
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Save changes" })
      ).toBeEnabled();
    });
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    const expectedAction = podActions.update({
      cpu_over_commit_ratio: 5,
      id: pod.id,
      memory_over_commit_ratio: 7,
      pool: 2,
      power_address: pod.power_parameters?.power_address,
      tags: "tag1,tag2",
      type: PodType.LXD,
      zone: 3,
    });
    await waitFor(() => {
      expect(
        store.getActions().find((action) => action.type === expectedAction.type)
      ).toStrictEqual(expectedAction);
    });
  });

  it("can handle updating a virsh KVM", async () => {
    const pod = factory.podDetails({
      id: 1,
      tags: ["tag1", "tag2"],
      type: PodType.VIRSH,
    });
    const { store } = renderWithProviders(<KVMConfigurationCard pod={pod} />, {
      state,
    });
    await waitFor(() => {
      expect(
        screen.getByRole("combobox", { name: "Zone" })
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("combobox", { name: "Zone" }));

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Zone" }),
      "3"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Resource pool" }),
      "2"
    );
    await userEvent.type(
      screen.getByLabelText("Password (optional)"),
      "password"
    );
    fireEvent.change(screen.getByRole("slider", { name: "CPU overcommit" }), {
      target: { value: "5" },
    });
    fireEvent.change(
      screen.getByRole("slider", { name: "Memory overcommit" }),
      {
        target: { value: "7" },
      }
    );
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Save changes" })
      ).toBeEnabled();
    });
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    const expectedAction = podActions.update({
      cpu_over_commit_ratio: 5,
      id: pod.id,
      memory_over_commit_ratio: 7,
      pool: 2,
      power_address: pod.power_parameters?.power_address,
      power_pass: "password",
      tags: "tag1,tag2",
      type: PodType.VIRSH,
      zone: 3,
    });
    await waitFor(() => {
      expect(
        store.getActions().find((action) => action.type === expectedAction.type)
      ).toStrictEqual(expectedAction);
    });
  });

  it("enables the submit button if form values are different to pod values", async () => {
    const pod = factory.podDetails({
      cpu_over_commit_ratio: 1,
      id: 1,
    });
    const { rerender } = renderWithProviders(
      <KVMConfigurationCard pod={pod} />,
      {
        state,
      }
    );

    // Submit should be disabled by default.
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();

    // Change value to something other than the initial.
    fireEvent.change(screen.getByRole("slider", { name: "CPU overcommit" }), {
      target: { value: (pod.cpu_over_commit_ratio + 1).toString() },
    });

    // Submit should be enabled.
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Save changes" })
      ).not.toBeDisabled();
    });

    // Update the pod with a new value.
    const updatedPod = {
      ...pod,
      cpu_over_commit_ratio: pod.cpu_over_commit_ratio + 1,
    };
    rerender(<KVMConfigurationCard pod={updatedPod} />);

    // Submit should be disabled again.
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });
});
