import VLANsList from "./VLANsList";

import type { RootState } from "@/app/store/root/types";
import {
  rootState as rootStateFactory,
  vlan as vlanFactory,
  vlanState as vlanStateFactory,
} from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("VLANsList", () => {
  let state: RootState;
  beforeEach(() => {
    state = rootStateFactory({
      vlan: vlanStateFactory({
        loading: false,
        loaded: true,
        items: [vlanFactory()],
      }),
    });
  });

  it("uses the correct window title", async () => {
    renderWithProviders(<VLANsList />, { state });

    expect(document.title).toBe("VLANs | MAAS");
  });

  it("renders the VLANs table", () => {
    renderWithProviders(<VLANsList />, { state });

    expect(
      screen.getByRole("grid", { name: "VLANs table" })
    ).toBeInTheDocument();
  });

  it("renders the EditVLAN form", async () => {
    renderWithProviders(<VLANsList />, { state });

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect(
      screen.getByRole("complementary", { name: "Edit VLAN" })
    ).toBeInTheDocument();
  });

  it("renders the DeleteVLAN form", async () => {
    renderWithProviders(<VLANsList />, { state });

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(
      screen.getByRole("complementary", { name: "Delete VLAN" })
    ).toBeInTheDocument();
  });
});
