import ComposeForm from "../ComposeForm";

import { PodType } from "@/app/store/pod/constants";
import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  zoneResolvers.listZones.handler(),
  poolsResolvers.listPools.handler()
);

const generateWrapper = async (state: RootState, pod: Pod) => {
  renderWithProviders(<ComposeForm hostId={pod.id} />, {
    state,
    initialEntries: [`/kvm/${pod.id}`],
  });
  await waitFor(() => {
    expect(zoneResolvers.listZones.resolved).toBeTruthy();
  });
};

describe("StorageTable", () => {
  let initialState: RootState;

  beforeEach(() => {
    const pod = factory.podDetails({ id: 1 });

    initialState = factory.rootState({
      domain: factory.domainState({
        loaded: true,
      }),
      fabric: factory.fabricState({
        loaded: true,
      }),
      general: factory.generalState({
        powerTypes: factory.powerTypesState({
          data: [factory.powerType()],
          loaded: true,
        }),
      }),
      pod: factory.podState({
        items: [pod],
        loaded: true,
        statuses: { [pod.id]: factory.podStatus() },
      }),
      space: factory.spaceState({
        loaded: true,
      }),
      subnet: factory.subnetState({
        loaded: true,
      }),
      vlan: factory.vlanState({
        loaded: true,
      }),
    });
  });

  it("disables add disk button if pod is composing a machine", async () => {
    const pod = factory.podDetails({ id: 1 });
    const state = { ...initialState };
    state.pod.items = [pod];
    state.pod.statuses = { [pod.id]: factory.podStatus({ composing: true }) };
    await generateWrapper(state, pod);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /add disk/i })
      ).toBeAriaDisabled();
    });
  });

  it("can add disks and remove all but last disk", async () => {
    const pod = factory.podDetails({
      default_storage_pool: "pool-1",
      id: 1,
      storage_pools: [factory.podStoragePool({ id: "pool-1" })],
      type: PodType.VIRSH,
    });
    const state = { ...initialState };
    state.pod.items = [pod];
    await generateWrapper(state, pod);

    // One disk should display by default and cannot be deleted
    await waitFor(() => {
      expect(screen.getAllByLabelText(/disk/i)).toHaveLength(1);
    });
    expect(
      screen.queryByRole("button", { name: /remove/i })
    ).not.toBeInTheDocument();

    // Click "Add disk" - another disk should be added, and remove button should enable
    await userEvent.click(screen.getByRole("button", { name: /add disk/i }));
    expect(screen.getAllByLabelText(/disk/i)).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /remove/i })).toHaveLength(2);

    // Click delete button - a disk should be removed
    await userEvent.click(
      screen.getAllByRole("button", { name: /remove/i })[0]
    );
    expect(screen.getAllByLabelText(/disk/i)).toHaveLength(1);
    expect(
      screen.queryByRole("button", { name: /remove/i })
    ).not.toBeInTheDocument();
  });

  it("displays a caution message if the boot disk size is less than 8GB", async () => {
    const pod = factory.podDetails({
      default_storage_pool: "pool-1",
      id: 1,
      storage_pools: [factory.podStoragePool({ id: "pool-1" })],
    });
    const state = { ...initialState };
    state.pod.items = [pod];
    await generateWrapper(state, pod);

    await waitFor(() => {
      expect(
        screen.getByRole("spinbutton", { name: "Size (GB)" })
      ).toBeInTheDocument();
    });

    const diskSizeInput = screen.getByRole("spinbutton", { name: "Size (GB)" });

    await userEvent.clear(diskSizeInput);
    await userEvent.type(diskSizeInput, "4");

    expect(
      screen.getByText("Ubuntu typically requires 8GB minimum.")
    ).toBeInTheDocument();
  });

  it("doesn't display a caution message if it isn't a boot disk and size is less than 8GB", async () => {
    const pod = factory.podDetails({
      default_storage_pool: "pool-1",
      id: 1,
      storage_pools: [factory.podStoragePool({ id: "pool-1" })],
    });
    const state = { ...initialState };
    state.pod.items = [pod];
    await generateWrapper(state, pod);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /add disk/i })
      ).toBeInTheDocument();
    });
    // Add a disk
    await userEvent.click(screen.getByRole("button", { name: /add disk/i }));
    // Change the second disk size to below 8GB
    const secondDiskSizeInput = screen.getAllByRole("spinbutton", {
      name: "Size (GB)",
    })[1];
    await userEvent.clear(secondDiskSizeInput);
    await userEvent.type(secondDiskSizeInput, "7");
    expect(
      screen.queryByText("Ubuntu typically requires 8GB minimum.")
    ).not.toBeInTheDocument();
  });

  it("displays an error message if disk size is higher than available storage in pool", async () => {
    const pool = factory.podStoragePool({ available: 20000000000 }); // 20GB
    const pod = factory.podDetails({
      id: 1,
      default_storage_pool: pool.id,
      storage_pools: [pool],
    });
    const state = { ...initialState };
    state.pod.items = [pod];
    await generateWrapper(state, pod);

    // Change the disk size to above 20GB
    await waitFor(() => {
      expect(
        screen.getByRole("spinbutton", { name: "Size (GB)" })
      ).toBeInTheDocument();
    });
    const diskSizeInput = screen.getByRole("spinbutton", { name: "Size (GB)" });
    await userEvent.clear(diskSizeInput);
    await userEvent.type(diskSizeInput, "21");

    expect(
      screen.getByText(`Only 20GB available in ${pool.name}.`)
    ).toBeInTheDocument();
  });

  it(`displays an error message if the sum of disk sizes from a pool is higher
    than the available storage in that pool`, async () => {
    const pool = factory.podStoragePool({ available: 25000000000 }); // 25GB
    const pod = factory.podDetails({
      id: 1,
      default_storage_pool: pool.id,
      storage_pools: [pool],
      type: PodType.VIRSH,
    });
    const state = { ...initialState };
    state.pod.items = [pod];
    await generateWrapper(state, pod);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /add disk/i })
      ).toBeInTheDocument();
    });
    // Add a disk
    await userEvent.click(screen.getByRole("button", { name: /add disk/i }));

    const diskSizeInputs = screen.getAllByRole("spinbutton", {
      name: "Size (GB)",
    });

    // Change the first disk size to 15GB
    await userEvent.clear(diskSizeInputs[0]);
    await userEvent.type(diskSizeInputs[0], "15");

    // Change the second disk size to 11GB
    await userEvent.clear(diskSizeInputs[1]);
    await userEvent.type(diskSizeInputs[1], "11");

    // Each is lower than 25GB, but the sum is higher, so an error should show
    expect(
      screen.getByText(`Only 25GB available in ${pool.name}.`)
    ).toBeInTheDocument();
  });

  it("displays an error message on render if not enough space", async () => {
    const pool = factory.podStoragePool({ available: 0, name: "pool" });
    const pod = factory.podDetails({
      id: 1,
      default_storage_pool: pool.id,
      storage_pools: [pool],
    });
    const state = { ...initialState };
    state.pod.items = [pod];
    await generateWrapper(state, pod);
    await waitFor(() => {
      expect(
        screen.getByText("Only 0GB available in pool.")
      ).toBeInTheDocument();
    });
  });
});
