import KVMResourcesCard from "./KVMResourcesCard";

import urls from "@/app/base/urls";
import { PodType } from "@/app/store/pod/constants";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("KVMResourcesCard", () => {
  it("shows a spinner if pods have not loaded yet", () => {
    const state = factory.rootState({
      pod: factory.podState({
        items: [],
        loaded: false,
      }),
    });
    renderWithProviders(<KVMResourcesCard id={1} />, {
      state,
      initialEntries: ["/kvm/1/project"],
    });

    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("links to the VMs tab for a LXD pod", () => {
    const state = factory.rootState({
      pod: factory.podState({
        items: [factory.pod({ id: 1, type: PodType.LXD })],
        loaded: true,
      }),
    });

    renderWithProviders(<KVMResourcesCard id={1} />, {
      state,
      initialEntries: ["/kvm/1/project"],
    });

    expect(screen.getByRole("link", { name: /Total VMs/ })).toHaveAttribute(
      "href",
      urls.kvm.lxd.single.vms({ id: 1 })
    );
  });

  it("displays VmResources for a Virsh pod", () => {
    const state = factory.rootState({
      pod: factory.podState({
        items: [factory.pod({ id: 1, type: PodType.VIRSH })],
        loaded: true,
      }),
    });

    renderWithProviders(<KVMResourcesCard id={1} />, {
      state,
      initialEntries: ["/kvm/1/project"],
    });

    expect(
      screen.getByRole("button", { name: /Resource VMs/ })
    ).toBeInTheDocument();
  });
});
