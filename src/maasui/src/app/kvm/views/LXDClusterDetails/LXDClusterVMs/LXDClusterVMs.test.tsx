import * as reduxToolkit from "@reduxjs/toolkit";

import LXDClusterVMs from "./LXDClusterVMs";

import urls from "@/app/base/urls";
import { machineActions } from "@/app/store/machine";
import * as query from "@/app/store/machine/utils/query";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

const callId = "mocked-nanoid";
vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

describe("LXDClusterVMs", () => {
  beforeEach(() => {
    vi.spyOn(query, "generateCallId").mockReturnValue(callId);
    vi.spyOn(reduxToolkit, "nanoid").mockReturnValue(callId);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders a link to a cluster's host's VM page", () => {
    const machine = factory.machine({
      pod: { id: 11, name: "podrick" },
      system_id: "abc123",
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [machine],
        lists: {
          [callId]: factory.machineStateList({
            loaded: true,
            groups: [
              factory.machineStateListGroup({
                items: [machine.system_id],
              }),
            ],
          }),
        },
      }),
      vmcluster: factory.vmClusterState({
        items: [
          factory.vmCluster({
            id: 1,
            virtual_machines: [factory.virtualMachine({ system_id: "abc123" })],
          }),
        ],
        loaded: true,
      }),
    });

    renderWithProviders(
      <LXDClusterVMs clusterId={1} searchFilter="" setSearchFilter={vi.fn()} />,
      {
        initialEntries: [urls.kvm.lxd.cluster.vms.index({ clusterId: 1 })],
        state,
      }
    );
    expect(screen.getByTestId("host-link")).toHaveAttribute(
      "href",
      urls.kvm.lxd.cluster.vms.host({ clusterId: 1, hostId: 11 })
    );
  });

  it("fetches VMs for the hosts", () => {
    const state = factory.rootState({
      vmcluster: factory.vmClusterState({
        items: [
          factory.vmCluster({
            id: 1,
            hosts: [
              factory.vmHost({ name: "host 1" }),
              factory.vmHost({ name: "host 2" }),
            ],
          }),
        ],
        loaded: true,
      }),
    });

    const { store } = renderWithProviders(
      <LXDClusterVMs clusterId={1} searchFilter="" setSearchFilter={vi.fn()} />,
      {
        initialEntries: [urls.kvm.lxd.cluster.vms.index({ clusterId: 1 })],
        state,
      }
    );
    const expected = machineActions.fetch(callId, {
      filter: { pod: ["host 1", "host 2"] },
    });
    const fetches = store
      .getActions()
      .filter((action) => action.type === expected.type);
    expect(fetches[fetches.length - 1].payload.params.filter).toStrictEqual({
      pod: ["host 1", "host 2"],
    });
  });
});
