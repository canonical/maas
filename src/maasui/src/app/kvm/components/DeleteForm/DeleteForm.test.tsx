import DeleteForm from "./DeleteForm";

import { PodType } from "@/app/store/pod/constants";
import podSelectors from "@/app/store/pod/selectors";
import vmClusterSelectors from "@/app/store/vmcluster/selectors";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("DeleteForm", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("can show the processing status when deleting the given pod", () => {
    const pod = factory.pod({ id: 1 });
    const state = factory.rootState({
      pod: factory.podState({
        items: [pod],
        statuses: factory.podStatuses({
          [pod.id]: factory.podStatus({ deleting: true }),
        }),
      }),
    });

    renderWithProviders(<DeleteForm hostId={1} />, {
      initialEntries: ["/kvm"],
      state,
    });

    expect(screen.getByTestId("saving-label")).toHaveTextContent(
      "Removing KVM host..."
    );
  });

  it("can show the processing status when deleting the given cluster", async () => {
    const cluster = factory.vmCluster({ id: 1 });
    const state = factory.rootState({
      vmcluster: factory.vmClusterState({
        items: [cluster],
        statuses: factory.vmClusterStatuses({
          deleting: true,
        }),
      }),
    });

    renderWithProviders(<DeleteForm clusterId={1} />, {
      initialEntries: ["/kvm"],
      state,
    });
    expect(screen.getByTestId("saving-label")).toHaveTextContent(
      "Removing cluster..."
    );
  });

  it("shows a decompose checkbox if deleting a LXD pod", async () => {
    const pod = factory.pod({ id: 1, type: PodType.LXD });
    const state = factory.rootState({
      pod: factory.podState({
        items: [pod],
        statuses: factory.podStatuses({
          [pod.id]: factory.podStatus({ deleting: false }),
        }),
      }),
    });

    renderWithProviders(<DeleteForm hostId={1} />, {
      initialEntries: ["/kvm"],
      state,
    });

    expect(
      screen.getByRole("checkbox", {
        name: "Selecting this option will delete all VMs in pod2 along with their storage.",
      })
    ).toBeInTheDocument();
  });

  it("shows a decompose checkbox if deleting a cluster", async () => {
    const cluster = factory.vmCluster({ id: 1 });
    const state = factory.rootState({
      vmcluster: factory.vmClusterState({
        items: [cluster],
        statuses: factory.vmClusterStatuses({
          deleting: false,
        }),
      }),
    });

    renderWithProviders(<DeleteForm clusterId={1} />, {
      initialEntries: ["/kvm"],
      state,
    });

    expect(
      screen.getByRole("checkbox", {
        name: "Selecting this option will delete all VMs in clusterA along with their storage.",
      })
    ).toBeInTheDocument();
  });

  it("does not show a decompose checkbox if deleting a non-LXD pod", async () => {
    const pod = factory.pod({ id: 1, type: PodType.VIRSH });
    const state = factory.rootState({
      pod: factory.podState({
        items: [pod],
        statuses: factory.podStatuses({
          [pod.id]: factory.podStatus({ deleting: false }),
        }),
      }),
    });

    renderWithProviders(<DeleteForm hostId={1} />, {
      initialEntries: ["/kvm"],
      state,
    });

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("correctly dispatches actions to delete given KVM", async () => {
    const pod = factory.pod({ id: 1 });
    const state = factory.rootState({
      pod: factory.podState({
        items: [pod],
        statuses: factory.podStatuses({
          [pod.id]: factory.podStatus({ deleting: false }),
        }),
      }),
    });

    const { store } = renderWithProviders(<DeleteForm hostId={1} />, {
      initialEntries: ["/kvm"],
      state,
    });

    expect(
      screen.getByRole("button", { name: /Remove KVM Host/i })
    ).toBeEnabled();
    await userEvent.click(
      screen.getByRole("button", { name: /Remove KVM Host/i })
    );

    expect(
      store.getActions().find((action) => action.type === "pod/delete")
    ).toStrictEqual({
      type: "pod/delete",
      meta: {
        model: "pod",
        method: "delete",
      },
      payload: {
        params: {
          decompose: false,
          id: pod.id,
        },
      },
    });
  });

  it("correctly dispatches actions to delete a cluster", async () => {
    const cluster = factory.vmCluster({ id: 1 });
    const state = factory.rootState({
      vmcluster: factory.vmClusterState({
        items: [cluster],
        statuses: factory.vmClusterStatuses({
          deleting: false,
        }),
      }),
    });

    const { store } = renderWithProviders(<DeleteForm clusterId={1} />, {
      initialEntries: ["/kvm"],
      state,
    });

    expect(
      screen.getByRole("button", { name: /Remove cluster/i })
    ).toBeEnabled();
    await userEvent.click(
      screen.getByRole("button", { name: /Remove cluster/i })
    );
    expect(
      store.getActions().find((action) => action.type === "vmcluster/delete")
    ).toStrictEqual({
      type: "vmcluster/delete",
      meta: {
        model: "vmcluster",
        method: "delete",
      },
      payload: {
        params: {
          decompose: false,
          id: cluster.id,
        },
      },
    });
  });

  it("sets the form to saved when a cluster has been deleted", () => {
    const cluster = factory.vmCluster({ id: 1 });
    const state = factory.rootState({
      vmcluster: factory.vmClusterState({
        items: [cluster],
        statuses: factory.vmClusterStatuses({
          deleting: true,
        }),
      }),
    });

    const Proxy = () => <DeleteForm clusterId={1} />;
    const { rerender } = renderWithProviders(<Proxy />, {
      initialEntries: ["/kvm"],
      state,
    });

    // Cluster is being deleted - form shouldn't be saved yet.
    expect(screen.getByTestId("saving-label")).toHaveTextContent(
      "Removing cluster..."
    );

    // Mock the change from deleting the cluster to no longer deleting the
    // cluster, then rerender the component.
    vi.spyOn(vmClusterSelectors, "status").mockReturnValue(false);
    rerender(<DeleteForm clusterId={1} />);

    // Form should have saved successfully.
    expect(screen.queryByTestId("saving-label")).not.toBeInTheDocument();
  });

  it("sets the form to saved when a pod has been deleted", () => {
    const pod = factory.pod({ id: 1, type: PodType.LXD });
    const state = factory.rootState({
      pod: factory.podState({
        items: [pod],
        statuses: factory.podStatuses({
          [pod.id]: factory.podStatus({ deleting: true }),
        }),
      }),
    });

    const Proxy = () => <DeleteForm hostId={1} />;
    const { rerender } = renderWithProviders(<Proxy />, {
      initialEntries: ["/kvm"],
      state,
    });

    // Pod is being deleted - form shouldn't be saved yet.
    expect(screen.getByTestId("saving-label")).toHaveTextContent(
      "Removing KVM host..."
    );

    // Mock the change from deleting the pod to no longer deleting the pod, then
    // rerender the component.
    vi.spyOn(podSelectors, "deleting").mockReturnValue([]);
    rerender(<DeleteForm hostId={1} />);

    // Form should have saved successfully.
    expect(screen.queryByTestId("saving-label")).not.toBeInTheDocument();
  });

  it("clusters do not get marked as deleted if there is an error", () => {
    const cluster = factory.vmCluster({ id: 1 });
    const state = factory.rootState({
      vmcluster: factory.vmClusterState({
        items: [cluster],
        statuses: factory.vmClusterStatuses({
          deleting: true,
        }),
      }),
    });

    const Proxy = () => <DeleteForm clusterId={1} />;
    const { rerender } = renderWithProviders(<Proxy />, {
      initialEntries: ["/kvm"],
      state,
    });

    // Cluster is being deleted - form shouldn't be saved yet.
    expect(screen.getByTestId("saving-label")).toHaveTextContent(
      "Removing cluster..."
    );

    // Mock the change from deleting the cluster to no longer deleting the
    // cluster including an error, then rerender the component.
    vi.spyOn(vmClusterSelectors, "status").mockReturnValue(false);
    vi.spyOn(vmClusterSelectors, "eventError").mockReturnValue([
      factory.vmClusterEventError({
        error: "Uh oh",
        event: "delete",
      }),
    ]);
    rerender(<DeleteForm clusterId={1} />);

    // Form should not have saved successfully.
    expect(screen.getByTestId("notification-title")).toHaveTextContent(
      "Error:"
    );
    expect(screen.getByText("Uh oh")).toBeInTheDocument();
  });

  it("pods do not get marked as deleted if there is an error", () => {
    const pod = factory.pod({ id: 1, type: PodType.LXD });
    const state = factory.rootState({
      pod: factory.podState({
        items: [pod],
        statuses: factory.podStatuses({
          [pod.id]: factory.podStatus({ deleting: true }),
        }),
      }),
    });

    const Proxy = () => <DeleteForm hostId={1} />;
    const { rerender } = renderWithProviders(<Proxy />, {
      initialEntries: ["/kvm"],
      state,
    });

    // Pod is being deleted - form shouldn't be saved yet.
    expect(screen.getByTestId("saving-label")).toHaveTextContent(
      "Removing KVM host..."
    );

    // Mock the change from deleting the pod to no longer deleting the pod
    // including an error, then rerender the component.
    vi.spyOn(podSelectors, "deleting").mockReturnValue([]);
    vi.spyOn(podSelectors, "errors").mockReturnValue("Uh oh");
    rerender(<DeleteForm hostId={1} />);

    // Form should not have saved successfully.
    expect(screen.getByTestId("notification-title")).toHaveTextContent(
      "Error:"
    );
    expect(screen.getByText("Uh oh")).toBeInTheDocument();
  });
});
