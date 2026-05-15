/* eslint-disable testing-library/prefer-presence-queries */

import ComposeForm from "../../ComposeForm";

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
  within,
} from "@/testing/utils";

setupMockServer(
  zoneResolvers.listZones.handler(),
  poolsResolvers.listPools.handler()
);

const renderComposeForm = async (state: RootState, pod: Pod) => {
  const view = renderWithProviders(<ComposeForm hostId={pod.id} />, {
    initialEntries: [`/kvm/${pod.id}`],
    state,
  });
  await waitFor(() => {
    expect(zoneResolvers.listZones.resolved).toBeTruthy();
  });
  return view;
};

describe("PoolSelect", () => {
  let state: RootState;

  beforeEach(() => {
    const pod = factory.podDetails({ id: 1 });

    state = factory.rootState({
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

  it(`correctly calculates allocated, requested, free and total space, where
    free space is rounded down`, async () => {
    const pool = factory.podStoragePool({ name: "pool" });
    const pod = factory.podDetails({
      id: 1,
      default_storage_pool: pool.id,
      storage_pools: [pool],
      resources: factory.podResources({
        storage_pools: {
          [pool.name]: factory.podStoragePoolResource({
            allocated_other: 4000000000, // 4GB
            allocated_tracked: 6000000000, // 6GB
            total: 19999000000, // 19.999GB
          }),
        },
      }),
    });
    state.pod.items = [pod];

    await renderComposeForm(state, pod);

    await waitFor(() =>
      expect(screen.getByRole("spinbutton", { name: "Size (GB)" }))
    );
    // Open PoolSelect dropdown and change disk size to 5GB
    const diskSizeInput = screen.getByRole("spinbutton", { name: "Size (GB)" });
    await userEvent.clear(diskSizeInput);
    await userEvent.type(diskSizeInput, "5");
    await userEvent.click(screen.getByRole("button", { name: "pool" }));

    // Allocated = 10GB
    expect(screen.getByTestId("allocated")).toHaveTextContent("10GB");
    // Requested = 5GB
    expect(screen.getByTestId("requested")).toHaveTextContent("5GB");
    // Free = available - requested = 9.999 - 5 = 4.999 rounded down = 4.99GB
    expect(screen.getByTestId("free")).toHaveTextContent("4.99GB");
    // Total = 19.999GB rounded automatically = 20GB
    expect(screen.getByTestId("total")).toHaveTextContent("20GB");
  });

  it("shows a tick next to the selected pool", async () => {
    const [defaultPool, otherPool] = [
      factory.podStoragePool({ name: "default" }),
      factory.podStoragePool({ name: "other" }),
    ];
    const pod = factory.podDetails({
      id: 1,
      default_storage_pool: defaultPool.id,
      resources: factory.podResources({
        storage_pools: {
          [defaultPool.name]: factory.podStoragePoolResource({
            allocated_other: 1000000000000,
            allocated_tracked: 2000000000000,
            total: 6000000000000,
          }),
          [otherPool.name]: factory.podStoragePoolResource({
            allocated_other: 1000000000000,
            allocated_tracked: 2000000000000,
            total: 6000000000000,
          }),
        },
      }),
      storage_pools: [defaultPool, otherPool],
    });
    state.pod.items = [pod];

    await renderComposeForm(state, pod);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "default" })
      ).toBeInTheDocument();
    });

    // Open PoolSelect dropdown
    await userEvent.click(screen.getByRole("button", { name: "default" }));

    // defaultPool should be selected by default
    expect(
      within(screen.getByTestId("kvm-pool-select-default")).getByLabelText(
        "selected"
      )
    ).toHaveClass("p-icon--tick");
    expect(
      within(screen.getByTestId("kvm-pool-select-other")).queryByLabelText(
        "selected"
      )
    ).not.toBeInTheDocument();

    // Select other pool
    await userEvent.click(screen.getByTestId("kvm-pool-select-other"));

    expect(
      screen
        .getByTestId("kvm-pool-select-default")
        .querySelector(".p-icon--tick")
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("kvm-pool-select-other").querySelector(".p-icon--tick")
    ).toBeInTheDocument();
  });

  it("disables a pool that does not have enough space for disk, with warning", async () => {
    const [poolWithSpace, poolWithoutSpace] = [
      factory.podStoragePool({ name: "pool-without-space" }),
      factory.podStoragePool({ name: "pool-with-space" }),
    ];
    const pod = factory.podDetails({
      id: 1,
      default_storage_pool: poolWithSpace.id,
      resources: factory.podResources({
        storage_pools: {
          [poolWithoutSpace.name]: factory.podStoragePoolResource({
            allocated_other: 0,
            allocated_tracked: 0,
            total: 100000000000, // 100GB free
          }),
          [poolWithSpace.name]: factory.podStoragePoolResource({
            allocated_other: 0,
            allocated_tracked: 90000000000,
            total: 100000000000, // 10GB free
          }),
        },
      }),
      storage_pools: [poolWithSpace, poolWithoutSpace],
    });
    state.pod.items = [pod];

    await renderComposeForm(state, pod);

    await waitFor(() => {
      expect(
        screen.getByRole("spinbutton", { name: "Size (GB)" })
      ).toBeInTheDocument();
    });

    // Open PoolSelect dropdown and change disk size to 50GB
    const diskSizeInput = screen.getByRole("spinbutton", { name: "Size (GB)" });
    await userEvent.clear(diskSizeInput);
    await userEvent.type(diskSizeInput, "50");
    await userEvent.click(
      screen.getByRole("button", { name: "pool-without-space" })
    );

    // poolWithSpace should not be disabled, but poolWithoutSpace should be
    expect(
      screen.getByTestId("kvm-pool-select-pool-with-space")
    ).not.toBeDisabled();
    expect(
      screen.getByTestId("kvm-pool-select-pool-without-space")
    ).toBeDisabled();
    expect(
      screen.getByText(/Only 10 GB available in pool-without-space/i)
    ).toBeInTheDocument();
  });
});
