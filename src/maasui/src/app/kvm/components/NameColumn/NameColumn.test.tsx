import NameColumn from "./NameColumn";

import urls from "@/app/base/urls";
import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("NameColumn", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState();
  });

  it("can display a link to Virsh pod's details page", () => {
    const pod = factory.pod({ id: 1, name: "pod-1", type: PodType.VIRSH });
    state.pod.items = [pod];

    renderWithProviders(
      <NameColumn
        name={pod.name}
        secondary={pod.power_parameters?.project}
        url={urls.kvm.virsh.details.index({ id: 1 })}
      />,
      { state }
    );

    expect(screen.getByRole("link", { name: "pod-1" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "pod-1" })).toHaveAttribute(
      "href",
      urls.kvm.virsh.details.index({ id: 1 })
    );
  });

  it("can display a link to a LXD pod's details page", () => {
    const pod = factory.pod({ id: 1, name: "pod-1", type: PodType.LXD });
    state.pod.items = [pod];

    renderWithProviders(
      <NameColumn
        name={pod.name}
        secondary={pod.power_parameters?.project}
        url={urls.kvm.lxd.single.index({ id: 1 })}
      />,
      { state }
    );

    expect(screen.getByRole("link", { name: "pod-1" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "pod-1" })).toHaveAttribute(
      "href",
      urls.kvm.lxd.single.index({ id: 1 })
    );
  });

  it("can show a secondary row", () => {
    const pod = factory.pod({
      id: 1,
      name: "pod-1",
      power_parameters: factory.podPowerParameters({
        project: "group-project",
      }),
      type: PodType.LXD,
    });
    state.pod.items = [pod];

    renderWithProviders(
      <NameColumn
        name={pod.name}
        secondary={pod.power_parameters?.project}
        url={urls.kvm.virsh.details.index({ id: 1 })}
      />,
      { state }
    );

    expect(screen.queryByTestId("power-address")).not.toBeInTheDocument();
    expect(screen.getByTestId("secondary")).toHaveTextContent("group-project");
  });
});
