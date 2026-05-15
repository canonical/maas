import BulkActions from "./BulkActions";

import CreateDatastore from "@/app/base/components/node/StorageTables/AvailableStorageTable/BulkActions/CreateDatastore";
import CreateRaid from "@/app/base/components/node/StorageTables/AvailableStorageTable/BulkActions/CreateRaid";
import CreateVolumeGroup from "@/app/base/components/node/StorageTables/AvailableStorageTable/BulkActions/CreateVolumeGroup";
import UpdateDatastore from "@/app/base/components/node/StorageTables/AvailableStorageTable/BulkActions/UpdateDatastore";
import { DiskTypes, StorageLayout } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import {
  expectTooltipOnHover,
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("BulkActions", () => {
  it("disables create volume group button with tooltip if selected devices are not eligible", async () => {
    const selected = [
      factory.nodeDisk({
        partitions: [factory.nodePartition()],
        type: DiskTypes.PHYSICAL,
      }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            disks: selected,
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(<BulkActions selected={selected} systemId="abc123" />, {
      state,
    });
    const createVolumeGroupButton = screen.getByRole("button", {
      name: "Create volume group",
    });
    expect(createVolumeGroupButton).toBeAriaDisabled();
    await expectTooltipOnHover(
      createVolumeGroupButton,
      "Select one or more unpartitioned and unformatted storage devices to create a volume group."
    );
  });

  it("enables create volume group button if selected devices are eligible", () => {
    const selected = [
      factory.nodeDisk({ partitions: null, type: DiskTypes.PHYSICAL }),
      factory.nodePartition({ filesystem: null }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(<BulkActions selected={selected} systemId="abc123" />, {
      state,
    });

    expect(
      screen.getByRole("button", { name: "Create volume group" })
    ).not.toBeAriaDisabled();
  });

  it("renders datastore bulk actions if the detected layout is a VMWare layout", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            detected_storage_layout: StorageLayout.VMFS7,
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(<BulkActions selected={[]} systemId="abc123" />, {
      state,
    });

    expect(screen.getByTestId("vmware-bulk-actions")).toBeInTheDocument();
  });

  it(`enables the create datastore button if at least one unpartitioned and
    unformatted device is selected`, () => {
    const selected = [factory.nodeDisk({ filesystem: null, partitions: null })];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            detected_storage_layout: StorageLayout.VMFS6,
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(<BulkActions selected={selected} systemId="abc123" />, {
      state,
    });

    expect(
      screen.getByRole("button", { name: "Create datastore" })
    ).not.toBeAriaDisabled();
  });

  it(`enables the add to existing datastore button if at least one unpartitioned
    and unformatted device is selected and at least one datastore exists`, () => {
    const datastore = factory.nodeDisk({
      filesystem: factory.nodeFilesystem({ fstype: "vmfs6" }),
    });
    const selected = factory.nodeDisk({ filesystem: null, partitions: null });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            detected_storage_layout: StorageLayout.VMFS6,
            disks: [datastore, selected],
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(
      <BulkActions selected={[selected]} systemId="abc123" />,
      { state }
    );

    expect(
      screen.getByRole("button", { name: "Add to existing datastore" })
    ).not.toBeAriaDisabled();
  });

  it("can trigger the create datastore sidepanel", async () => {
    const datastore = factory.nodeDisk({
      filesystem: factory.nodeFilesystem({ fstype: "vmfs6" }),
    });
    const selected = factory.nodeDisk({ filesystem: null, partitions: null });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            detected_storage_layout: StorageLayout.VMFS6,
            disks: [datastore, selected],
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(
      <BulkActions selected={[selected]} systemId="abc123" />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Create datastore" })
    );
    expect(mockOpen).toHaveBeenCalledWith(
      expect.objectContaining({
        component: CreateDatastore,
      })
    );
  });

  it("can trigger the create RAID sidepanel", async () => {
    const selected = [
      factory.nodeDisk({
        filesystem: null,
        type: DiskTypes.VIRTUAL,
      }),
      factory.nodeDisk({
        filesystem: null,
        type: DiskTypes.VIRTUAL,
      }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            detected_storage_layout: StorageLayout.FLAT,
            disks: selected,
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(<BulkActions selected={selected} systemId="abc123" />, {
      state,
    });

    await userEvent.click(screen.getByRole("button", { name: "Create RAID" }));
    expect(mockOpen).toHaveBeenCalledWith(
      expect.objectContaining({
        component: CreateRaid,
      })
    );
  });

  it("can trigger the create volume group sidepanel", async () => {
    const selected = [
      factory.nodeDisk({
        filesystem: null,
        type: DiskTypes.VIRTUAL,
      }),
      factory.nodeDisk({
        filesystem: null,
        type: DiskTypes.VIRTUAL,
      }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            detected_storage_layout: StorageLayout.FLAT,
            disks: selected,
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
    renderWithProviders(<BulkActions selected={selected} systemId="abc123" />, {
      state,
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Create volume group" })
    );
    expect(mockOpen).toHaveBeenCalledWith(
      expect.objectContaining({
        component: CreateVolumeGroup,
      })
    );
  });

  it("can trigger the update datastore sidepanel", async () => {
    const datastore = factory.nodeDisk({
      filesystem: factory.nodeFilesystem({ fstype: "vmfs6" }),
    });
    const selected = factory.nodeDisk({ filesystem: null, partitions: null });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            detected_storage_layout: StorageLayout.VMFS6,
            disks: [datastore, selected],
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });

    renderWithProviders(
      <BulkActions selected={[selected]} systemId="abc123" />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Add to existing datastore" })
    );
    expect(mockOpen).toHaveBeenCalledWith(
      expect.objectContaining({
        component: UpdateDatastore,
      })
    );
  });
});
