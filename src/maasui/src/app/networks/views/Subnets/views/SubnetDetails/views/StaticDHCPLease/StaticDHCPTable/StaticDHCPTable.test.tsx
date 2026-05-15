import DeleteDHCPLease from "../DeleteDHCPLease";
import ReserveDHCPLease from "../ReserveDHCPLease";

import StaticDHCPTable from "./StaticDHCPTable";

import { reservedIp } from "@/testing/factories/reservedip";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("StaticDHCPTable", () => {
  it("renders a loading component if table items are loading", async () => {
    renderWithProviders(
      <StaticDHCPTable loading={true} reservedIps={[]} subnetId={0} />
    );
    await waitFor(() => {
      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });
  });

  it("renders a message when table is empty", async () => {
    renderWithProviders(
      <StaticDHCPTable loading={false} reservedIps={[]} subnetId={0} />
    );
    await waitFor(() => {
      expect(
        screen.getByText("No static DHCP leases available.")
      ).toBeInTheDocument();
    });
  });

  it("renders the columns correctly", async () => {
    renderWithProviders(
      <StaticDHCPTable loading={false} reservedIps={[]} subnetId={0} />
    );
    [
      "IP Address",
      "MAC Address",
      "Node",
      "Interface",
      "Usage",
      "Comment",
      "Actions",
    ].forEach((column) => {
      expect(
        screen.getByRole("columnheader", {
          name: new RegExp(`^${column}`, "i"),
        })
      ).toBeInTheDocument();
    });
  });

  it("opens the side panel with the correct view when the edit button is clicked", async () => {
    const reservedIps = [reservedIp()];
    renderWithProviders(
      <StaticDHCPTable loading={false} reservedIps={reservedIps} subnetId={0} />
    );

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect(mockOpen).toHaveBeenCalledWith({
      component: ReserveDHCPLease,
      title: "Edit DHCP lease",
      props: {
        reservedIpId: reservedIps[0].id,
        subnetId: 0,
      },
    });
  });

  it("opens the side panel with the correct view when the delete button is clicked", async () => {
    const reservedIps = [reservedIp()];
    renderWithProviders(
      <StaticDHCPTable loading={false} reservedIps={reservedIps} subnetId={0} />
    );

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(mockOpen).toHaveBeenCalledWith({
      component: DeleteDHCPLease,
      title: "Delete DHCP lease",
      props: {
        reservedIpId: reservedIps[0].id,
      },
    });
  });
});
