import StorageTables, { Labels } from "./StorageTables";

import { DiskTypes, StorageLayout } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

it("renders a list of cache sets if any exist", () => {
  const node = factory.machineDetails({
    disks: [
      factory.nodeDisk({ name: "quiche-cache", type: DiskTypes.CACHE_SET }),
    ],
    system_id: "abc123",
  });
  const state = factory.rootState({
    machine: factory.machineState({
      items: [node],
    }),
  });

  renderWithProviders(<StorageTables canEditStorage node={node} />, {
    state,
  });

  expect(
    screen.getByRole("heading", { name: Labels.CacheSets })
  ).toBeInTheDocument();
});

it("renders a list of datastores if the detected layout is VMFS6", () => {
  const node = factory.machineDetails({
    system_id: "abc123",
    detected_storage_layout: StorageLayout.VMFS6,
    disks: [
      factory.nodeDisk({
        filesystem: factory.nodeFilesystem({
          fstype: "vmfs6",
          mount_point: "/path",
        }),
        name: "datastore1",
        size: 100,
      }),
    ],
  });
  const state = factory.rootState({
    machine: factory.machineState({
      items: [node],
    }),
  });

  renderWithProviders(<StorageTables canEditStorage node={node} />, {
    state,
  });

  expect(
    screen.getByRole("heading", { name: Labels.Datastores })
  ).toBeInTheDocument();
});
