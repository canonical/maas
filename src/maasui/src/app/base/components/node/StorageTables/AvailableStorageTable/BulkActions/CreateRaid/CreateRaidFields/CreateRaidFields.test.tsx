import CreateRaid from "../CreateRaid";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

describe("CreateRaidFields", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
  });

  it("can handle RAID 0 devices", async () => {
    const disks = [
      factory.nodeDisk({ available_size: 1000000000 }), // 1GB
      factory.nodeDisk({ available_size: 1500000000 }), // 1.5GB
    ];
    state.machine.items[0] = factory.machineDetails({
      disks,
      system_id: "abc123",
    });
    renderWithProviders(<CreateRaid selected={disks} systemId="abc123" />, {
      state,
    });

    await userEvent.selectOptions(
      screen.getByLabelText("RAID level"),
      "RAID 0"
    );

    // RAID 0s should not allow spare devices
    expect(screen.queryByTestId("max-spares")).not.toBeInTheDocument();
    // RAID 0 size is calculated as (minSize * numActive) = 1GB * 2 disks
    expect(screen.getByTestId("raid-size")).toHaveValue("2 GB");
  });

  it("can handle RAID 1 devices", async () => {
    const disks = [
      factory.nodeDisk({ available_size: 1000000000 }), // 1GB
      factory.nodeDisk({ available_size: 1500000000 }), // 1.5GB
      factory.nodeDisk({ available_size: 2000000000 }), // 2GB
    ];
    state.machine.items[0] = factory.machineDetails({
      disks,
      system_id: "abc123",
    });
    renderWithProviders(<CreateRaid selected={disks} systemId="abc123" />, {
      state,
    });

    await userEvent.selectOptions(
      screen.getByLabelText("RAID level"),
      "RAID 1"
    );

    // RAID 1s allow spare devices, with a minimum of 2 active
    expect(
      screen.getByRole("columnheader", { name: "Spare (max 1)" })
    ).toBeInTheDocument();
    // RAID 1 size is calculated as (minSize) = 1GB
    expect(screen.getByTestId("raid-size")).toHaveValue("1 GB");
  });

  it("can handle RAID 1 devices", async () => {
    const disks = [
      factory.nodeDisk({ available_size: 1000000000 }), // 1GB
      factory.nodeDisk({ available_size: 1500000000 }), // 1.5GB
      factory.nodeDisk({ available_size: 2000000000 }), // 2GB
    ];
    state.machine.items[0] = factory.machineDetails({
      disks,
      system_id: "abc123",
    });
    renderWithProviders(<CreateRaid selected={disks} systemId="abc123" />, {
      state,
    });

    await userEvent.selectOptions(
      screen.getByLabelText("RAID level"),
      "RAID 1"
    );
    // RAID 1s allow spare devices, with a minimum of 2 active
    expect(
      screen.getByRole("columnheader", { name: "Spare (max 1)" })
    ).toBeInTheDocument();
    // RAID 1 size is calculated as (minSize) = 1GB
    expect(screen.getByTestId("raid-size")).toHaveValue("1 GB");
  });

  it("can handle RAID 5 devices", async () => {
    const disks = [
      factory.nodeDisk({ available_size: 1000000000 }), // 1GB
      factory.nodeDisk({ available_size: 1500000000 }), // 1.5GB
      factory.nodeDisk({ available_size: 2000000000 }), // 2GB
      factory.nodeDisk({ available_size: 2500000000 }), // 2.5GB
    ];
    state.machine.items[0] = factory.machineDetails({
      disks,
      system_id: "abc123",
    });
    renderWithProviders(<CreateRaid selected={disks} systemId="abc123" />, {
      state,
    });

    await userEvent.selectOptions(
      screen.getByLabelText("RAID level"),
      "RAID 5"
    );

    // RAID 5s allow spare devices, with a minimum of 3 active
    expect(
      screen.getByRole("columnheader", { name: "Spare (max 1)" })
    ).toBeInTheDocument();
    // RAID 5 size is calculated as minSize * (numActive - 1) = 1GB * (4 - 1)
    expect(screen.getByTestId("raid-size")).toHaveValue("3 GB");
  });

  it("can handle RAID 6 devices", async () => {
    const disks = [
      factory.nodeDisk({ available_size: 1000000000 }), // 1GB
      factory.nodeDisk({ available_size: 1500000000 }), // 1.5GB
      factory.nodeDisk({ available_size: 2000000000 }), // 2GB
      factory.nodeDisk({ available_size: 2500000000 }), // 2.5GB
      factory.nodeDisk({ available_size: 3000000000 }), // 3GB
    ];
    state.machine.items[0] = factory.machineDetails({
      disks,
      system_id: "abc123",
    });
    renderWithProviders(<CreateRaid selected={disks} systemId="abc123" />, {
      state,
    });

    await userEvent.selectOptions(
      screen.getByLabelText("RAID level"),
      "RAID 6"
    );

    // RAID 6s allow spare devices, with a minimum of 4 active
    expect(
      screen.getByRole("columnheader", { name: "Spare (max 1)" })
    ).toBeInTheDocument();
    // RAID 6 size is calculated as minSize * (numActive - 2) = 1GB * (5 - 2)
    expect(screen.getByTestId("raid-size")).toHaveValue("3 GB");
  });

  it("can handle RAID 10 devices", async () => {
    const disks = [
      factory.nodeDisk({ available_size: 1500000000 }), // 1.5GB
      factory.nodeDisk({ available_size: 2000000000 }), // 2GB
      factory.nodeDisk({ available_size: 2500000000 }), // 2.5GB
      factory.nodeDisk({ available_size: 3000000000 }), // 3GB
    ];
    state.machine.items[0] = factory.machineDetails({
      disks,
      system_id: "abc123",
    });
    renderWithProviders(<CreateRaid selected={disks} systemId="abc123" />, {
      state,
    });

    await userEvent.selectOptions(
      screen.getByLabelText("RAID level"),
      "RAID 10"
    );

    // RAID 10s allow spare devices, with a minimum of 3 active
    expect(
      screen.getByRole("columnheader", { name: "Spare (max 1)" })
    ).toBeInTheDocument();
    // RAID 10 size is calculated as (minSize * numActive) / 2 = (1.5GB * 4) / 2
    expect(screen.getByTestId("raid-size")).toHaveValue("3 GB");
  });

  it("can handle setting spare disks and partitions", async () => {
    const partitions = [
      factory.nodePartition({ size: 1000000000 }), // 1GB
      factory.nodePartition({ size: 1500000000 }), // 1.5GB
    ];
    const disks = [
      factory.nodeDisk({ available_size: 2000000000 }), // 2GB
      factory.nodeDisk({ available_size: 2500000000 }), // 2.5GB
      factory.nodeDisk({ partitions }),
    ];
    state.machine.items[0] = factory.machineDetails({
      disks,
      system_id: "abc123",
    });
    renderWithProviders(
      <CreateRaid
        selected={[disks[0], disks[1], ...partitions]}
        systemId="abc123"
      />,
      { state }
    );
    const isActive = (i: number) =>
      within(screen.getAllByTestId("active-status")[i]).queryByTestId(
        "is-active"
      );
    const getCheckbox = (i: number) => screen.getAllByRole("checkbox")[i];

    await userEvent.selectOptions(
      screen.getByLabelText("RAID level"),
      "RAID 1"
    );

    // Wait for the spare column to appear after RAID level change
    await waitFor(() => {
      expect(
        screen.getByRole("columnheader", { name: "Spare (max 2)" })
      ).toBeInTheDocument();
    });

    // Click out of  select
    await userEvent.click(
      screen.getByRole("columnheader", { name: "Spare (max 2)" })
    );

    // None of the spare checkboxes should be disabled.
    expect(getCheckbox(0)).not.toBeDisabled();
    expect(getCheckbox(1)).not.toBeDisabled();
    expect(getCheckbox(2)).not.toBeDisabled();
    expect(getCheckbox(3)).not.toBeDisabled();

    // Check the spare checkboxes for the first disk and first partition
    const diskId = `raid-${disks[0].type}-${disks[0].id}`;
    const partitionId = `raid-${partitions[0].type}-${partitions[0].id}`;
    await userEvent.click(screen.getByTestId(diskId));
    await userEvent.click(screen.getByTestId(partitionId));

    // First disk and partition should be spare, second disk and partition
    // should be active.
    expect(isActive(0)).not.toBeInTheDocument();
    expect(isActive(1)).toBeInTheDocument();
    expect(isActive(2)).not.toBeInTheDocument();
    expect(isActive(3)).toBeInTheDocument();

    // Should not be able to select any more spare devices, but should still
    // be able to unselect existing spares.
    expect(getCheckbox(0)).not.toBeDisabled();
    expect(getCheckbox(1)).toBeDisabled();
    expect(getCheckbox(2)).not.toBeDisabled();
    expect(getCheckbox(3)).toBeDisabled();
  });

  it("resets block/partition and spare block/partition values on RAID level change", async () => {
    const partitions = [
      factory.nodePartition({ size: 1000000000 }), // 1GB
      factory.nodePartition({ size: 1500000000 }), // 1.5GB
    ];
    const disks = [
      factory.nodeDisk({ available_size: 2000000000 }), // 2GB
      factory.nodeDisk({ available_size: 2500000000 }), // 2.5GB
      factory.nodeDisk({ partitions }),
    ];
    state.machine.items[0] = factory.machineDetails({
      disks,
      system_id: "abc123",
    });
    renderWithProviders(
      <CreateRaid
        selected={[disks[0], disks[1], ...partitions]}
        systemId="abc123"
      />,
      { state }
    );
    const isActive = (i: number) =>
      within(screen.getAllByTestId("active-status")[i]).queryByTestId(
        "is-active"
      );

    await userEvent.selectOptions(
      screen.getByLabelText("RAID level"),
      "RAID 1"
    );

    // Click out of  select
    await userEvent.click(
      screen.getByRole("columnheader", { name: "Spare (max 2)" })
    );

    // Check the spare checkboxes for the first disk and first partition
    const diskId = `raid-${disks[0].type}-${disks[0].id}`;
    const partitionId = `raid-${partitions[0].type}-${partitions[0].id}`;
    await userEvent.click(screen.getByTestId(diskId));
    await userEvent.click(screen.getByTestId(partitionId));

    // First disk and partition should be spare, second disk and partition
    // should be active
    expect(isActive(0)).not.toBeInTheDocument();
    expect(isActive(1)).toBeInTheDocument();
    expect(isActive(2)).not.toBeInTheDocument();
    expect(isActive(3)).toBeInTheDocument();

    // Change to RAID 5
    await userEvent.selectOptions(
      screen.getByLabelText("RAID level"),
      "RAID 5"
    );

    // All should be reset to active.
    expect(isActive(0)).toBeInTheDocument();
    expect(isActive(1)).toBeInTheDocument();
    expect(isActive(2)).toBeInTheDocument();
    expect(isActive(3)).toBeInTheDocument();
  });
});
