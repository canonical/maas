import LXDHostVMs from "./LXDHostVMs";

import ComposeForm from "@/app/kvm/components/ComposeForm";
import { machineActions } from "@/app/store/machine";
import * as factory from "@/testing/factories";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("LXDHostVMs", () => {
  it("shows a spinner if pod has not loaded yet", () => {
    const state = factory.rootState({
      pod: factory.podState({
        items: [],
        loaded: false,
      }),
    });

    renderWithProviders(
      <LXDHostVMs hostId={1} searchFilter="" setSearchFilter={vi.fn()} />,
      { state }
    );

    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("can view resources by NUMA node", async () => {
    const state = factory.rootState({
      pod: factory.podState({
        items: [
          factory.pod({
            id: 1,
            resources: factory.podResources({ numa: [factory.podNuma()] }),
          }),
        ],
      }),
    });

    renderWithProviders(
      <LXDHostVMs hostId={1} searchFilter="" setSearchFilter={vi.fn()} />,
      { state }
    );

    expect(screen.queryByTestId("numa-resources")).not.toBeInTheDocument();

    await userEvent.click(screen.getByTestId("numa-switch"));

    expect(screen.getByTestId("numa-resources")).toBeInTheDocument();
  });

  it("displays the host name when in a cluster", async () => {
    const pod = factory.pod({ id: 1, name: "cluster host" });
    const state = factory.rootState({
      pod: factory.podState({
        items: [pod],
      }),
    });
    renderWithProviders(
      <LXDHostVMs
        clusterId={2}
        hostId={1}
        searchFilter=""
        setSearchFilter={vi.fn()}
      />,
      { state }
    );
    expect(screen.getByTestId("toolbar-title")).toHaveTextContent(
      `VMs on ${pod.name}`
    );
  });

  it("does not display the host name when in a single host", async () => {
    const pod = factory.pod({ id: 1, name: "cluster host" });
    const state = factory.rootState({
      pod: factory.podState({
        items: [pod],
      }),
    });
    renderWithProviders(
      <LXDHostVMs hostId={1} searchFilter="" setSearchFilter={vi.fn()} />,
      { state }
    );
    expect(screen.getByTestId("toolbar-title")).toHaveTextContent(
      `VMs on this host`
    );
  });

  it("can open the compose VM form", async () => {
    const pod = factory.pod({ id: 1 });
    const state = factory.rootState({
      pod: factory.podState({
        items: [pod],
      }),
    });

    renderWithProviders(
      <LXDHostVMs hostId={1} searchFilter="" setSearchFilter={vi.fn()} />,
      { state }
    );

    await userEvent.click(screen.getByRole("button", { name: "Add VM" }));

    expect(mockOpen).toHaveBeenCalledWith({
      component: ComposeForm,
      title: "Compose",
      props: {
        hostId: 1,
      },
    });
  });

  it("fetches VMs for the host", async () => {
    const pod = factory.pod({ id: 1, name: "cluster host" });
    const state = factory.rootState({
      pod: factory.podState({
        items: [pod],
      }),
    });

    const { store } = renderWithProviders(
      <LXDHostVMs hostId={1} searchFilter="" setSearchFilter={vi.fn()} />,
      { state }
    );
    const expected = machineActions.fetch("123456", {
      filter: { pod: [pod.name] },
    });

    const fetches = store
      .getActions()
      .filter((action) => action.type === expected.type);
    expect(fetches[fetches.length - 1].payload.params.filter).toStrictEqual({
      pod: [pod.name],
    });
  });
});
