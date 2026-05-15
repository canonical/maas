import { NameColumn } from "./NameColumn";

import type { RootState } from "@/app/store/root/types";
import { NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

describe("NameColumn", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machine({
            domain: factory.modelRef({
              name: "example",
            }),
            extra_macs: [],
            fqdn: "koala.example",
            hostname: "koala",
            ip_addresses: [],
            pool: factory.modelRef(),
            pxe_mac: "00:11:22:33:44:55",
            status: NodeStatus.RELEASING,
            system_id: "abc123",
            zone: factory.modelRef(),
          }),
        ],
      }),
    });
  });

  it("can be locked", () => {
    state.machine.items[0].locked = true;
    renderWithProviders(<NameColumn groupValue={null} systemId="abc123" />, {
      state,
    });
    expect(screen.getByLabelText("Locked")).toHaveClass("p-icon--locked");
  });

  it("can show the FQDN", () => {
    renderWithProviders(<NameColumn groupValue={null} systemId="abc123" />, {
      state,
    });
    expect(screen.getByRole("link", { name: /koala*/i })).toBeInTheDocument();
  });

  it("can show a single ip address", () => {
    state.machine.items[0].ip_addresses = [{ ip: "127.0.0.1", is_boot: false }];
    renderWithProviders(<NameColumn groupValue={null} systemId="abc123" />, {
      state,
    });
    expect(screen.getByTestId("ip-addresses")).toHaveTextContent("127.0.0.1");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("can show multiple ip addresses", async () => {
    state.machine.items[0].ip_addresses = [
      { ip: "127.0.0.1", is_boot: false },
      { ip: "127.0.0.2", is_boot: false },
    ];
    renderWithProviders(<NameColumn groupValue={null} systemId="abc123" />, {
      state,
    });
    expect(screen.getByTestId("ip-addresses")).toHaveTextContent("127.0.0.1");
    const button = screen.getByRole("button", { name: "+1" });
    expect(button).toBeInTheDocument();

    await userEvent.hover(button);
    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toBeInTheDocument();
    });
  });

  it("can show a PXE ip address", () => {
    state.machine.items[0].ip_addresses = [{ is_boot: true, ip: "127.0.0.1" }];
    renderWithProviders(<NameColumn groupValue={null} systemId="abc123" />, {
      state,
    });
    expect(screen.getByTestId("ip-addresses")).toHaveTextContent(
      "127.0.0.1 (PXE)"
    );
  });

  it("doesn't show duplicate ip addresses", () => {
    state.machine.items[0].ip_addresses = [
      { ip: "127.0.0.1", is_boot: false },
      { ip: "127.0.0.1", is_boot: false },
    ];
    renderWithProviders(<NameColumn groupValue={null} systemId="abc123" />, {
      state,
    });
    expect(screen.getByTestId("ip-addresses")).toHaveTextContent("127.0.0.1");
    expect(
      screen.queryByRole("button", { name: "+1" })
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId("Tooltip")).not.toBeInTheDocument();
  });

  it("can show a single mac address", () => {
    renderWithProviders(
      <NameColumn groupValue={null} showMAC={true} systemId="abc123" />,
      { state }
    );
    expect(screen.getByRole("link")).toHaveTextContent("00:11:22:33:44:55");
  });

  it("can show multiple mac address", () => {
    state.machine.items[0].extra_macs = ["aa:bb:cc:dd:ee:ff"];
    renderWithProviders(
      <NameColumn groupValue={null} showMAC={true} systemId="abc123" />,
      { state }
    );
    expect(screen.getAllByRole("link")).toHaveLength(2);
    expect(screen.getAllByRole("link")[1]).toHaveTextContent(/\(\+1\)/);
  });

  it("can render a machine with minimal data", () => {
    state.machine.items[0] = factory.machine({
      domain: factory.modelRef({
        name: "example",
      }),
      fqdn: "koala.example",
      hostname: "koala",
      system_id: "abc123",
    });
    renderWithProviders(<NameColumn groupValue={null} systemId="abc123" />, {
      state,
    });
    expect(screen.getByRole("link", { name: /koala*/i })).toBeInTheDocument();
  });

  it("can render a machine in the MAC state with minimal data", () => {
    state.machine.items[0] = factory.machine({
      domain: factory.modelRef({
        name: "example",
      }),
      hostname: "koala",
      pxe_mac: "00:11:22:33:44:55",
      system_id: "abc123",
    });
    renderWithProviders(
      <NameColumn groupValue={null} showMAC={true} systemId="abc123" />,
      { state }
    );

    expect(
      screen.getByText(`${state.machine.items[0].pxe_mac}`)
    ).toBeInTheDocument();
  });

  it("does not render checkbox if onToggleMenu not provided", () => {
    renderWithProviders(<NameColumn groupValue={null} systemId="abc123" />, {
      state,
    });
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});
