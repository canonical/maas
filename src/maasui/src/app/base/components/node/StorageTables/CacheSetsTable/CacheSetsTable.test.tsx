import CacheSetsTable from "./CacheSetsTable";

import DeleteCacheSet from "@/app/base/components/node/StorageTables/AvailableStorageTable/DeleteCacheSet";
import { DiskTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
  within,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("CacheSetsTable", () => {
  it("only shows disks that are cache sets", () => {
    const [cacheSet, notCacheSet] = [
      factory.nodeDisk({
        name: "quiche",
        type: DiskTypes.CACHE_SET,
      }),
      factory.nodeDisk({
        name: "frittata",
        type: DiskTypes.PHYSICAL,
      }),
    ];
    const machine = factory.machineDetails({
      disks: [cacheSet, notCacheSet],
      system_id: "abc123",
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [machine],
      }),
    });
    renderWithProviders(<CacheSetsTable canEditStorage node={machine} />, {
      state,
    });

    const rows = within(screen.getAllByRole("rowgroup")[1]).getAllByRole("row");
    expect(rows).toHaveLength(1);
    expect(within(rows[0]).getAllByRole("cell")[0]).toHaveTextContent(
      cacheSet.name
    );
  });

  it("does not show an action column if node is a controller", () => {
    const controller = factory.controllerDetails({
      disks: [
        factory.nodeDisk({
          name: "quiche",
          type: DiskTypes.CACHE_SET,
        }),
      ],
      system_id: "abc123",
    });
    const state = factory.rootState({
      controller: factory.controllerState({
        items: [controller],
      }),
    });
    renderWithProviders(
      <CacheSetsTable canEditStorage={false} node={controller} />,
      {
        state,
      }
    );

    expect(
      screen.queryByRole("columnheader", { name: "actions" })
    ).not.toBeInTheDocument();
  });

  it("shows an action column if node is a machine", () => {
    const machine = factory.machineDetails({
      disks: [
        factory.nodeDisk({
          name: "quiche",
          type: DiskTypes.CACHE_SET,
        }),
      ],
      system_id: "abc123",
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [machine],
      }),
    });
    renderWithProviders(<CacheSetsTable canEditStorage node={machine} />, {
      state,
    });

    expect(
      screen.getByRole("columnheader", { name: "actions" })
    ).toBeInTheDocument();
  });

  it("can open the side panel to delete a cache set if node is a machine", async () => {
    const disk = factory.nodeDisk({
      type: DiskTypes.CACHE_SET,
    });
    const machine = factory.machineDetails({
      disks: [disk],
      system_id: "abc123",
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [machine],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(<CacheSetsTable canEditStorage node={machine} />, {
      state,
    });

    await userEvent.click(screen.getByRole("button", { name: /Take action/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "Remove cache set..." })
    );

    expect(mockOpen).toHaveBeenCalledWith(
      expect.objectContaining({
        component: DeleteCacheSet,
        props: {
          disk,
          systemId: machine.system_id,
        },
      })
    );
  });
});
