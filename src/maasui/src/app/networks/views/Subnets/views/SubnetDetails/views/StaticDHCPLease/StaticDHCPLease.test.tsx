import StaticDHCPLease from "./StaticDHCPLease";

import { renderWithProviders, screen } from "@/testing/utils";

describe("StaticDHCPLease", () => {
  it("renders", () => {
    renderWithProviders(<StaticDHCPLease subnetId={1} />);
    expect(
      screen.getByRole("heading", { name: "Static DHCP leases" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Reserve static DHCP lease" })
    ).toBeInTheDocument();
  });
});
