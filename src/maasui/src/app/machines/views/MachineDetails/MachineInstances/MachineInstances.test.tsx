import MachineInstances from "./MachineInstances";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("MachineInstances", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            system_id: "abc123",
            devices: [
              factory.machineDevice({
                fqdn: "instance1",
                interfaces: [
                  factory.machineInterface({
                    mac_address: "f5:f6:9b:7c:1b:85",
                    links: [
                      factory.networkLink({
                        ip_address: "1.2.3.99",
                      }),
                    ],
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
    });
  });

  it("displays the spinner on load", () => {
    renderWithProviders(<MachineInstances />, {
      state,
    });

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/loading.../i)).toBeInTheDocument();
  });

  it("displays the table when data is available", () => {
    renderWithProviders(<MachineInstances />, {
      state,
      initialEntries: ["/machine/abc123/instances"],
      pattern: "/machine/:id/instances",
    });

    expect(
      screen.getByRole("grid", { name: /machine instances/i })
    ).toBeInTheDocument();
  });

  it("displays instance with mac address and ip address correctly", () => {
    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        devices: [
          factory.machineDevice({
            fqdn: "foo",
            interfaces: [
              factory.machineInterface({
                mac_address: "00:00:9b:7c:1b:85",
                links: [
                  factory.networkLink({
                    ip_address: "100.100.3.99",
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
    ];

    renderWithProviders(<MachineInstances />, {
      state,
      initialEntries: ["/machine/abc123/instances"],
      pattern: "/machine/:id/instances",
    });

    expect(screen.getByTestId("name")).toHaveTextContent("foo");
    expect(screen.getByTestId("mac")).toHaveTextContent("00:00:9b:7c:1b:85");
    expect(screen.getByTestId("ip")).toHaveTextContent("100.100.3.99");
  });

  it("displays instance with mac address correctly", () => {
    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        devices: [
          factory.machineDevice({
            fqdn: "foo",
            interfaces: [
              factory.machineInterface({
                mac_address: "00:00:9b:7c:1b:85",
              }),
            ],
          }),
        ],
      }),
    ];

    renderWithProviders(<MachineInstances />, {
      state,
      initialEntries: ["/machine/abc123/instances"],
      pattern: "/machine/:id/instances",
    });

    expect(screen.getByTestId("name")).toHaveTextContent("foo");
    expect(screen.getByTestId("mac")).toHaveTextContent("00:00:9b:7c:1b:85");
    expect(screen.getByTestId("ip")).toHaveTextContent("");
  });

  it("displays multiple instances", () => {
    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        devices: [
          factory.machineDevice({
            fqdn: "foo",
            interfaces: [
              factory.machineInterface({
                mac_address: "00:00:9b:7c:1b:85",
              }),
            ],
          }),
          factory.machineDevice({
            fqdn: "bar",
            interfaces: [
              factory.machineInterface({
                mac_address: "00:00:9b:7c:1b:85",
              }),
            ],
          }),
          factory.machineDevice({
            fqdn: "baz",
            interfaces: [
              factory.machineInterface({
                mac_address: "00:00:9b:7c:1b:85",
              }),
            ],
          }),
        ],
      }),
    ];

    renderWithProviders(<MachineInstances />, {
      state,
      initialEntries: ["/machine/abc123/instances"],
      pattern: "/machine/:id/instances",
    });

    expect(screen.getAllByTestId("name")).toHaveLength(3);
  });

  it("displays instances with multiple mac addresses", () => {
    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        devices: [
          factory.machineDevice({
            fqdn: "foo",
            interfaces: [
              factory.machineInterface({
                mac_address: "00:00:9b:7c:1b:85",
              }),
              factory.machineInterface({
                mac_address: "00:00:9b:7c:1b:01",
              }),
            ],
          }),
        ],
      }),
    ];

    renderWithProviders(<MachineInstances />, {
      state,
      initialEntries: ["/machine/abc123/instances"],
      pattern: "/machine/:id/instances",
    });

    expect(screen.getAllByTestId("mac")).toHaveLength(2);
    expect(screen.getAllByTestId("name").at(0)).toHaveTextContent("foo");
    expect(screen.getAllByTestId("mac").at(0)).toHaveTextContent(
      "00:00:9b:7c:1b:85"
    );
    expect(screen.getAllByTestId("ip").at(0)).toHaveTextContent("");
    expect(screen.getAllByTestId("name").at(1)).toHaveTextContent("");
    expect(screen.getAllByTestId("mac").at(1)).toHaveTextContent(
      "00:00:9b:7c:1b:01"
    );
    expect(screen.getAllByTestId("ip").at(1)).toHaveTextContent("");
  });

  it("displays instances with multiple ip addresses", () => {
    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        devices: [
          factory.machineDevice({
            fqdn: "foo",
            interfaces: [
              factory.machineInterface({
                mac_address: "00:00:9b:7c:1b:85",
                links: [
                  factory.networkLink({
                    ip_address: "1.2.3.4",
                  }),
                  factory.networkLink({
                    ip_address: "1.2.3.5",
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
    ];

    renderWithProviders(<MachineInstances />, {
      state,
      initialEntries: ["/machine/abc123/instances"],
      pattern: "/machine/:id/instances",
    });

    expect(screen.getAllByTestId("mac")).toHaveLength(2);
    expect(screen.getAllByTestId("name").at(0)).toHaveTextContent("foo");
    expect(screen.getAllByTestId("mac").at(0)).toHaveTextContent(
      "00:00:9b:7c:1b:85"
    );
    expect(screen.getAllByTestId("ip").at(0)).toHaveTextContent("1.2.3.4");
    expect(screen.getAllByTestId("name").at(1)).toHaveTextContent("");
    expect(screen.getAllByTestId("mac").at(1)).toHaveTextContent("");
    expect(screen.getAllByTestId("ip").at(1)).toHaveTextContent("1.2.3.5");
  });
});
