import { waitFor } from "@testing-library/react";
import type { Mock } from "vitest";

import LXDVMsTable from "./LXDVMsTable";

import { machineActions } from "@/app/store/machine";
import { FetchGroupKey, FetchSortDirection } from "@/app/store/machine/types";
import * as query from "@/app/store/machine/utils/query";
import { generateCallId } from "@/app/store/machine/utils/query";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

describe("LXDVMsTable", () => {
  let getResources: Mock;

  beforeEach(() => {
    vi.spyOn(query, "generateCallId").mockReturnValue("123456");
    getResources = vi.fn().mockReturnValue({
      hugepagesBacked: false,
      pinnedCores: [],
      unpinnedCores: 0,
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("display", () => {
    it("shows an add VM button if function provided", () => {
      const state = factory.rootState();

      renderWithProviders(
        <LXDVMsTable
          getResources={vi.fn()}
          onAddVMClick={vi.fn()}
          pods={["pod1"]}
          searchFilter=""
          setSearchFilter={vi.fn()}
        />,
        { state, initialEntries: ["/kvm/1/project"] }
      );
      expect(
        screen.getByRole("button", { name: "Add VM" })
      ).toBeInTheDocument();
    });

    it("does not show an add VM button if no function provided", () => {
      const state = factory.rootState();

      renderWithProviders(
        <LXDVMsTable
          getResources={vi.fn()}
          pods={["pod1"]}
          searchFilter=""
          setSearchFilter={vi.fn()}
        />,
        { state, initialEntries: ["/kvm/1/project"] }
      );

      expect(
        screen.queryByRole("button", { name: "Add VM" })
      ).not.toBeInTheDocument();
    });

    it("shows a message if no VMs in a KVM host match the search filter", () => {
      const state = factory.rootState({
        machine: factory.machineState({
          items: [],
        }),
      });

      renderWithProviders(
        <LXDVMsTable
          getResources={getResources}
          pods={["pod-1"]}
          searchFilter=""
          setSearchFilter={vi.fn()}
        />,
        {
          state,
          initialEntries: ["/kvm/1/project"],
        }
      );

      expect(
        screen.getByText(/No VMs in this KVM host match the search criteria/i)
      ).toBeInTheDocument();
    });

    it("shows a message if no VMs in a cluster match the search filter", () => {
      const state = factory.rootState({
        machine: factory.machineState({
          items: [],
        }),
      });

      renderWithProviders(
        <LXDVMsTable
          displayForCluster={true}
          getResources={getResources}
          pods={["pod-1"]}
          searchFilter=""
          setSearchFilter={vi.fn()}
        />,
        {
          state,
          initialEntries: ["/kvm/1/project"],
        }
      );

      expect(
        screen.getByText(/No VMs in this cluster match the search criteria/i)
      ).toBeInTheDocument();
    });

    it("renders a column for the host if function provided to render it", () => {
      const state = factory.rootState();

      renderWithProviders(
        <LXDVMsTable
          getHostColumn={vi.fn()}
          getResources={getResources}
          pods={["pod-1"]}
          searchFilter=""
          setSearchFilter={vi.fn()}
        />,
        {
          state,
          initialEntries: ["/kvm/1/project"],
        }
      );

      expect(
        screen.getByRole("columnheader", { name: /KVM host/i })
      ).toBeInTheDocument();
    });

    it("does not render a column for the host if no function provided to render it", () => {
      const state = factory.rootState();

      renderWithProviders(
        <LXDVMsTable
          getHostColumn={undefined}
          getResources={getResources}
          pods={["pod-1"]}
          searchFilter=""
          setSearchFilter={vi.fn()}
        />,
        {
          state,
          initialEntries: ["/kvm/1/project"],
        }
      );

      expect(
        screen.queryByRole("columnheader", { name: /KVM host/i })
      ).not.toBeInTheDocument();
    });

    it("displays tag names", async () => {
      const vms = [factory.machine({ tags: [1, 2] })];
      const pod = factory.pod({
        id: 1,
        name: "pod-1",
        resources: factory.podResources({
          vms: vms.map((vm) => factory.podVM({ system_id: vm.system_id })),
        }),
      });

      const state = factory.rootState({
        machine: factory.machineState({
          items: vms,
          lists: {
            "123456": factory.machineStateList({
              loaded: true,
              groups: [
                factory.machineStateListGroup({
                  items: vms.map(({ system_id }) => system_id),
                }),
              ],
            }),
          },
        }),
        tag: factory.tagState({
          items: [
            factory.tag({ id: 1, name: "tag1" }),
            factory.tag({ id: 2, name: "tag2" }),
          ],
        }),
        pod: factory.podState({ items: [pod], loaded: true }),
      });

      renderWithProviders(
        <LXDVMsTable
          getResources={getResources}
          pods={["pod-1"]}
          searchFilter=""
          setSearchFilter={vi.fn()}
        />,
        { state, initialEntries: ["/kvm/1/project"] }
      );

      expect(screen.getByText("tag1, tag2")).toBeInTheDocument();
    });

    it("shows a message if table is empty", () => {
      const state = factory.rootState({
        machine: factory.machineState({
          items: [],
        }),
      });

      renderWithProviders(
        <LXDVMsTable
          getResources={getResources}
          pods={["pod-1"]}
          searchFilter=""
          setSearchFilter={vi.fn()}
        />,
        {
          state,
          initialEntries: ["/kvm/1/project"],
        }
      );

      expect(
        screen.getByText(/No VMs in this KVM host match the search criteria/i)
      ).toBeInTheDocument();
    });
  });

  describe("actions", () => {
    it("fetches machines on load", () => {
      const state = factory.rootState();

      const { store } = renderWithProviders(
        <LXDVMsTable
          getResources={vi.fn()}
          onAddVMClick={vi.fn()}
          pods={["pod1"]}
          searchFilter=""
          setSearchFilter={vi.fn()}
        />,
        { state, initialEntries: ["/kvm/1/project"] }
      );

      const options = {
        filter: { pod: ["pod1"] },
        group_collapsed: undefined,
        group_key: null,
        page_number: 1,
        page_size: 10,
        sort_direction: FetchSortDirection.Ascending,
        sort_key: FetchGroupKey.Hostname,
      };
      const expectedAction = machineActions.fetch(generateCallId(options), {
        ...options,
      });
      expect(
        store.getActions().find((action) => action.type === expectedAction.type)
      ).toStrictEqual(expectedAction);
    });

    it("clears machine selected state on unmount", async () => {
      const state = factory.rootState();

      const {
        result: { unmount },
        store,
      } = renderWithProviders(
        <LXDVMsTable
          getResources={vi.fn()}
          onAddVMClick={vi.fn()}
          pods={["pod1"]}
          searchFilter=""
          setSearchFilter={vi.fn()}
        />,
        { state, initialEntries: ["/kvm/1/project"] }
      );

      unmount();

      const expectedAction = machineActions.setSelected(null);
      expect(
        store.getActions().find((action) => action.type === expectedAction.type)
      ).toStrictEqual(expectedAction);
    });

    it("can dispatch an action to select all VMs", async () => {
      const pod = factory.pod({ id: 1, name: "pod-1" });
      const vms = [
        factory.machine({
          system_id: "abc123",
        }),
        factory.machine({
          system_id: "def456",
        }),
      ];
      const state = factory.rootState({
        machine: factory.machineState({
          items: vms,
          lists: {
            "123456": factory.machineStateList({
              loaded: true,
              groups: [
                factory.machineStateListGroup({
                  items: vms.map(({ system_id }) => system_id),
                }),
              ],
            }),
          },
        }),
        pod: factory.podState({ items: [pod], loaded: true }),
      });

      const { store } = renderWithProviders(
        <LXDVMsTable
          getResources={getResources}
          pods={["pod-1"]}
          searchFilter=""
          setSearchFilter={vi.fn()}
        />,
        { state, initialEntries: ["/kvm/1/project"] }
      );

      await userEvent.click(
        screen.getByRole("checkbox", { name: /select all/i })
      );

      await waitFor(() => {
        expect(
          store
            .getActions()
            .find((action) => action.type === "machine/setSelected")
        ).toStrictEqual({
          type: "machine/setSelected",
          payload: { items: [vms[0].system_id, vms[1].system_id] },
        });
      });
    });

    it("can dispatch an action to unselect all VMs", async () => {
      const pod = factory.pod({ id: 1, name: "pod-1" });
      const vms = [
        factory.machine({
          system_id: "abc123",
        }),
        factory.machine({
          system_id: "def456",
        }),
      ];
      const state = factory.rootState({
        machine: factory.machineState({
          items: vms,
          selected: { items: vms.map((vm) => vm.system_id) },
        }),
        pod: factory.podState({ items: [pod], loaded: true }),
      });

      const { store } = renderWithProviders(
        <LXDVMsTable
          getResources={getResources}
          pods={["pod-1"]}
          searchFilter=""
          setSearchFilter={vi.fn()}
        />,
        { state, initialEntries: ["/kvm/1/project"] }
      );

      await userEvent.click(
        screen.getByRole("checkbox", { name: /select all/i })
      );

      await waitFor(() => {
        expect(
          store
            .getActions()
            .find((action) => action.type === "machine/setSelected")
        ).toStrictEqual({
          type: "machine/setSelected",
          payload: { items: [] },
        });
      });
    });
  });
});
