import NumaResourcesCard from "./NumaResourcesCard";

import { machineActions } from "@/app/store/machine";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, within } from "@/testing/utils";

describe("NumaResourcesCard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches machines on load", () => {
    const numaNode = factory.podNuma({ node_id: 111 });
    const pod = factory.pod({
      id: 1,
      resources: factory.podResources({
        numa: [numaNode],
      }),
    });
    const state = factory.rootState({
      pod: factory.podState({ items: [pod] }),
    });
    const { store } = renderWithProviders(
      <NumaResourcesCard numaId={111} podId={1} />,
      {
        state,
      }
    );

    const expectedAction = machineActions.fetch("mocked-nanoid");
    expect(
      store.getActions().some((action) => action.type === expectedAction.type)
    ).toBe(true);
  });

  it("aggregates the individual NUMA hugepages memory", () => {
    const pod = factory.pod({
      id: 1,
      resources: factory.podResources({
        numa: [
          factory.podNuma({
            memory: factory.podNumaMemory({
              hugepages: [
                factory.podNumaHugepageMemory({
                  allocated: 1,
                  free: 2,
                  page_size: 1024,
                }),
                factory.podNumaHugepageMemory({
                  allocated: 4,
                  free: 5,
                  page_size: 1024,
                }),
              ],
            }),
            node_id: 11,
          }),
        ],
      }),
    });
    const state = factory.rootState({
      pod: factory.podState({ items: [pod] }),
    });

    renderWithProviders(<NumaResourcesCard numaId={11} podId={1} />, { state });

    const hugepagesData = screen.getByRole("row", {
      name: new RegExp(`^Hugepage`, "i"),
    });
    expect(within(hugepagesData).getByText("(Size: 1KiB)")).toBeInTheDocument();
    expect(within(hugepagesData).getAllByRole("cell")[1]).toHaveTextContent(
      "5B"
    ); // Allocated
    expect(within(hugepagesData).getAllByRole("cell")[2]).toHaveTextContent(
      "7B"
    ); // Free
  });

  it("filters interface resources to those that belong to the NUMA node", () => {
    const podInterfaces = [
      factory.podNetworkInterface({ id: 11, name: "eth0" }),
      factory.podNetworkInterface({ id: 22, name: "eth1" }),
      factory.podNetworkInterface({ id: 33, name: "eth2" }),
    ];
    const numaNode = factory.podNuma({ interfaces: [11, 33], node_id: 111 });
    const pod = factory.pod({
      id: 1,
      resources: factory.podResources({
        interfaces: podInterfaces,
        numa: [numaNode],
      }),
    });
    const state = factory.rootState({
      pod: factory.podState({ items: [pod] }),
    });

    renderWithProviders(<NumaResourcesCard numaId={111} podId={1} />, {
      state,
    });

    expect(screen.getByText(/eth0/i)).toBeInTheDocument();
    expect(screen.queryByText(/eth1/i)).not.toBeInTheDocument();
    expect(screen.getByText(/eth2/i)).toBeInTheDocument();
  });

  it("correctly filters VMs dropdown to those that belong to each NUMA node", () => {
    const podID = 1;
    const podName = "pod";
    const machines = [
      factory.machine({
        pod: { id: podID, name: podName },
        system_id: "abc123",
      }),
      factory.machine({
        pod: { id: podID, name: podName },
        system_id: "def456",
      }),
      factory.machine({
        pod: { id: podID, name: podName },
        system_id: "ghi789",
      }),
    ];
    const pod = factory.pod({
      id: podID,
      name: podName,
      resources: factory.podResources({
        numa: [factory.podNuma({ node_id: 11, vms: [111, 333] })],
        vms: [
          factory.podVM({ id: 111, system_id: "abc123" }),
          factory.podVM({ id: 222, system_id: "def456" }),
          factory.podVM({ id: 333, system_id: "ghi789" }),
        ],
      }),
    });
    const state = factory.rootState({
      machine: factory.machineState({ items: machines }),
      pod: factory.podState({ items: [pod] }),
    });
    const { store } = renderWithProviders(
      <NumaResourcesCard numaId={11} podId={1} />,
      { state }
    );

    const expected = machineActions.fetch("mocked-nanoid");
    const result = store
      .getActions()
      .find((action) => action.type === expected.type);
    expect(result.payload.params.filter).toStrictEqual({
      id: [machines[0].system_id, machines[2].system_id],
      pod: [podName],
    });
  });
});
