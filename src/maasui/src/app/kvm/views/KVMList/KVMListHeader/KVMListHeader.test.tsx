import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import KVMListHeader from "./KVMListHeader";

import urls from "@/app/base/urls";
import AddLxd from "@/app/kvm/components/AddLxd";
import AddVirsh from "@/app/kvm/components/AddVirsh";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { mockSidePanel, renderWithProviders } from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("KVMListHeader", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      pod: factory.podState({
        loaded: true,
        items: [factory.pod({ id: 1 }), factory.pod({ id: 2 })],
      }),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("displays a loader if pods have not loaded", () => {
    state.pod.loaded = false;

    renderWithProviders(<KVMListHeader title="some text" />, { state });
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("displays a pod count if pods have loaded", () => {
    state.pod.loaded = true;

    renderWithProviders(<KVMListHeader title="some text" />, { state });
    expect(screen.getByText("2 KVM hosts available")).toBeInTheDocument();
  });

  it("can open the add LXD form at the LXD URL", async () => {
    renderWithProviders(<KVMListHeader title="LXD" />, {
      initialEntries: [{ pathname: urls.kvm.lxd.index, key: "testKey" }],
      state,
    });
    expect(
      screen.getByRole("button", { name: "Add LXD host" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Add Virsh host" })
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add LXD host" }));
    expect(mockOpen).toHaveBeenCalledWith({
      component: AddLxd,
      title: "Add LXD host",
    });
  });

  it("can open the add Virsh form at the Virsh URL", async () => {
    renderWithProviders(<KVMListHeader title="Virsh" />, {
      initialEntries: [{ pathname: urls.kvm.virsh.index, key: "testKey" }],
      state,
    });
    expect(
      screen.getByRole("button", { name: "Add Virsh host" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Add LXD host" })
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Add Virsh host" })
    );
    expect(mockOpen).toHaveBeenCalledWith({
      component: AddVirsh,
      title: "Add Virsh host",
    });
  });
});
