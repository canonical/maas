import NodeSummaryNetworkCard from "./NodeSummaryNetworkCard";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, within } from "@/testing/utils";

describe("NodeSummaryNetworkCard", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      device: factory.deviceState({ loaded: true }),
      fabric: factory.fabricState({ loaded: true }),
      vlan: factory.vlanState({ loaded: true }),
      subnet: factory.subnetState({ loaded: true }),
    });
  });

  it("fetches the necessary data on load", () => {
    const { store } = renderWithProviders(
      <NodeSummaryNetworkCard
        interfaces={[]}
        networkURL="url"
        node={state.device.items[0]}
      />,
      { state }
    );
    const actions = store.getActions();

    expect(actions.some((action) => action.type === "fabric/fetch"));
    expect(actions.some((action) => action.type === "vlan/fetch"));
    expect(actions.some((action) => action.type === "subnet/fetch"));
  });

  it("shows a spinner while network data is loading", () => {
    renderWithProviders(
      <NodeSummaryNetworkCard
        interfaces={null}
        networkURL="url"
        node={state.device.items[0]}
      />,
      { state }
    );

    expect(screen.getByTestId("loading-network-data")).toBeInTheDocument();
  });

  it("displays product, vendor and firmware information, if they exist", () => {
    const interfaces = [
      factory.networkInterface({
        firmware_version: "1.0.0",
        product: "Product 1",
        vendor: "Vendor 1",
      }),
      factory.networkInterface({
        firmware_version: null,
        product: null,
        vendor: null,
      }),
    ];
    renderWithProviders(
      <NodeSummaryNetworkCard
        interfaces={interfaces}
        networkURL="url"
        node={state.device.items[0]}
      />,
      { state }
    );

    expect(screen.getAllByTestId("nic-vendor")[0]).toHaveTextContent(
      "Vendor 1"
    );
    expect(screen.getAllByTestId("nic-product")[0]).toHaveTextContent(
      "Product 1"
    );
    expect(screen.getAllByTestId("nic-firmware-version")[0]).toHaveTextContent(
      "1.0.0"
    );
    expect(screen.getAllByTestId("nic-vendor")[1]).toHaveTextContent(
      "Unknown network card"
    );
  });

  it("groups interfaces by vendor, product and firmware version", () => {
    const interfaces = [
      ...Array.from(Array(4)).map(() =>
        factory.networkInterface({
          firmware_version: "1.0.0",
          product: "Product 1",
          vendor: "Vendor 1",
        })
      ),
      ...Array.from(Array(3)).map(() =>
        factory.networkInterface({
          firmware_version: "2.0.0",
          product: "Product 1",
          vendor: "Vendor 1",
        })
      ),
      ...Array.from(Array(2)).map(() =>
        factory.networkInterface({
          firmware_version: "2.0.0",
          product: "Product 2",
          vendor: "Vendor 1",
        })
      ),
      factory.networkInterface({
        firmware_version: "2.0.0",
        product: "Product 2",
        vendor: "Vendor 2",
      }),
    ];
    renderWithProviders(
      <NodeSummaryNetworkCard
        interfaces={interfaces}
        networkURL="url"
        node={state.device.items[0]}
      />,
      { state }
    );

    const tables = screen.getAllByRole("grid");

    expect(within(tables[0]).getAllByRole("row")).toHaveLength(5);
    expect(within(tables[1]).getAllByRole("row")).toHaveLength(4);
    expect(within(tables[2]).getAllByRole("row")).toHaveLength(3);
    expect(within(tables[3]).getAllByRole("row")).toHaveLength(2);
  });

  it("can render children", () => {
    renderWithProviders(
      <NodeSummaryNetworkCard
        interfaces={[]}
        networkURL="url"
        node={state.device.items[0]}
      >
        <span data-testid="child">Hi</span>
      </NodeSummaryNetworkCard>,
      { state }
    );

    expect(screen.getByTestId("child")).toBeInTheDocument();
  });
});
