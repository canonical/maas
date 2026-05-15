import ComposeForm, {
  createInterfaceConstraints,
  createStorageConstraints,
  getDefaultPoolLocation,
} from "./ComposeForm";

import { PodType } from "@/app/store/pod/constants";
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
  poolsResolvers.listPools.handler(),
  zoneResolvers.listZones.handler()
);

describe("ComposeForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      domain: factory.domainState({
        loaded: true,
        items: [
          factory.domain({
            id: 0,
            name: "unimaginative-name",
          }),
        ],
      }),
      fabric: factory.fabricState({
        loaded: true,
      }),
      general: factory.generalState({
        powerTypes: factory.powerTypesState({ loaded: true }),
      }),
      pod: factory.podState({
        items: [factory.podDetails({ id: 1, name: "blablabla" })],
        loaded: true,
        statuses: { 1: factory.podStatus() },
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

  it("fetches the necessary data on load", () => {
    const { store } = renderWithProviders(<ComposeForm hostId={1} />, {
      initialEntries: ["/kvm/1"],
      state,
    });
    const expectedActions = [
      "FETCH_DOMAIN",
      "FETCH_FABRIC",
      "general/fetchPowerTypes",
      "resourcepool/fetch",
      "space/fetch",
      "subnet/fetch",
      "vlan/fetch",
      "zone/fetch",
      "GET_POD",
    ];
    const actions = store.getActions();
    expectedActions.forEach((expectedAction) => {
      expect(actions.some((action) => action.type === expectedAction));
    });
  });

  it("displays a spinner if data has not loaded", () => {
    state.domain.loaded = false;
    renderWithProviders(<ComposeForm hostId={1} />, {
      initialEntries: ["/kvm/1"],
      state,
    });
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("can compose a machine without pinned cores", async () => {
    const pod = factory.podDetails({
      name: "podpodpodpodpod",
      id: 1,
      default_storage_pool: "1",
      memory_over_commit_ratio: 1,
      cpu_over_commit_ratio: 1,
      resources: factory.podResources({
        cores: {
          allocated_other: 0,
          allocated_tracked: 0,
          free: 16,
        },
        memory: {
          hugepages: {
            allocated_other: 0,
            allocated_tracked: 0,
            free: 8589934592,
          },
          general: {
            allocated_other: 0,
            allocated_tracked: 0,
            free: 8589934592,
          },
        },
      }),
      storage_pools: [
        factory.podStoragePool({
          id: "1",
          name: "pool-1",
          available: 80000000000,
        }),
        factory.podStoragePool({ name: "pool-2", available: 20000000000 }),
      ],
      type: "lxd",
    });
    const space = factory.space({ id: 1, name: "outer" });
    const subnet = factory.subnet({ id: 10, cidr: "192.168.1.1/24" });
    state.pod.items = [pod];
    state.space.items = [space];
    state.subnet.items = [subnet];

    const { store } = renderWithProviders(<ComposeForm hostId={1} />, {
      initialEntries: ["/kvm/1"],
      state,
    });
    await waitFor(() => {
      expect(
        screen.getByRole("textbox", { name: "VM name" })
      ).toBeInTheDocument();
    });

    await userEvent.clear(screen.getByRole("textbox", { name: "VM name" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "VM name" }),
      "mean-bean-machine"
    );
    await userEvent.clear(screen.getByRole("spinbutton", { name: "Cores" }));
    await userEvent.type(
      screen.getByRole("spinbutton", { name: "Cores" }),
      "5"
    );
    await userEvent.clear(
      screen.getByRole("spinbutton", { name: "RAM (MiB)" })
    );
    await userEvent.type(
      screen.getByRole("spinbutton", { name: "RAM (MiB)" }),
      "4096"
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Show advanced/i })
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Enable hugepages" })
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Domain" }),
      "0"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Zone" }),
      "3"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Resource pool" }),
      "2"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Architecture" }),
      "amd64/generic"
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Compose machine" })
    );

    expect(
      store.getActions().find((action) => action.type === "pod/compose")
    ).toStrictEqual({
      type: "pod/compose",
      meta: {
        method: "compose",
        model: "pod",
      },
      payload: {
        params: {
          architecture: "amd64/generic",
          cores: 5,
          domain: 0,
          hostname: "mean-bean-machine",
          hugepages_backed: true,
          id: 1,
          interfaces: "",
          memory: 4096,
          pool: 2,
          storage: "1:8(pool-1)",
          zone: 3,
        },
      },
    });
  });

  it("can compose a machine with pinned cores", async () => {
    const pod = factory.podDetails({
      name: "podpodpodpodpod",
      id: 1,
      default_storage_pool: "1",
      memory_over_commit_ratio: 1,
      cpu_over_commit_ratio: 1,
      resources: factory.podResources({
        cores: {
          allocated_other: 0,
          allocated_tracked: 0,
          free: 16,
        },
        memory: {
          hugepages: {
            allocated_other: 0,
            allocated_tracked: 0,
            free: 8589934592,
          },
          general: {
            allocated_other: 0,
            allocated_tracked: 0,
            free: 8589934592,
          },
        },
      }),
      storage_pools: [
        factory.podStoragePool({
          id: "1",
          name: "pool-1",
          available: 80000000000,
        }),
        factory.podStoragePool({ name: "pool-2", available: 20000000000 }),
      ],
      type: "lxd",
    });
    const space = factory.space({ id: 1, name: "outer" });
    const subnet = factory.subnet({ id: 10, cidr: "192.168.1.1/24" });
    state.pod.items = [pod];
    state.space.items = [space];
    state.subnet.items = [subnet];

    const { store } = renderWithProviders(<ComposeForm hostId={1} />, {
      initialEntries: ["/kvm/1"],
      state,
    });
    await waitFor(() => {
      expect(
        screen.getByRole("textbox", { name: "VM name" })
      ).toBeInTheDocument();
    });

    await userEvent.clear(screen.getByRole("textbox", { name: "VM name" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: "VM name" }),
      "mean-bean-machine"
    );
    await userEvent.click(
      screen.getByRole("radio", { name: "Pin VM to specific core(s)" })
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Pinned cores" }),
      "1,3"
    );
    await userEvent.clear(
      screen.getByRole("spinbutton", { name: "RAM (MiB)" })
    );
    await userEvent.type(
      screen.getByRole("spinbutton", { name: "RAM (MiB)" }),
      "4096"
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Show advanced/i })
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Enable hugepages" })
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Domain" }),
      "0"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Zone" }),
      "3"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Resource pool" }),
      "2"
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Architecture" }),
      "amd64/generic"
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Compose machine" })
    );

    expect(
      store.getActions().find((action) => action.type === "pod/compose")
    ).toStrictEqual({
      type: "pod/compose",
      meta: {
        method: "compose",
        model: "pod",
      },
      payload: {
        params: {
          architecture: "amd64/generic",
          domain: 0,
          hostname: "mean-bean-machine",
          hugepages_backed: true,
          id: 1,
          interfaces: "",
          memory: 4096,
          pinned_cores: [1, 3],
          pool: 2,
          storage: "1:8(pool-1)",
          zone: 3,
        },
      },
    });
  });

  describe("createInterfacesConstraint", () => {
    it("returns an empty string if no interfaces are given", () => {
      expect(createInterfaceConstraints([], [], [])).toEqual("");
    });

    it("returns an empty string if no constraints are given", () => {
      const interfaceFields = [
        {
          id: 1,
          ipAddress: "",
          name: "eth0",
          space: "",
          subnet: "",
        },
      ];
      expect(createInterfaceConstraints(interfaceFields, [], [])).toEqual("");
    });

    it("can create a single interface constraint", () => {
      const space = factory.space();
      const subnet = factory.subnet();
      const interfaceFields = [
        {
          id: 1,
          ipAddress: "192.168.1.1",
          name: "eth0",
          space: `${space.id}`,
          subnet: `${subnet.id}`,
        },
      ];
      expect(
        createInterfaceConstraints(interfaceFields, [space], [subnet])
      ).toEqual(
        `eth0:ip=${interfaceFields[0].ipAddress},space=${space.name},subnet_cidr=${subnet.cidr}`
      );
    });

    it("can create multiple interface constraints", () => {
      const [space1, space2] = [factory.space(), factory.space()];
      const [subnet1, subnet2] = [factory.subnet(), factory.subnet()];
      const [interface1, interface2] = [
        {
          id: 1,
          ipAddress: "192.168.1.1",
          name: "eth0",
          space: `${space1.id}`,
          subnet: `${subnet1.id}`,
        },
        {
          id: 2,
          ipAddress: "192.168.1.2",
          name: "eth1",
          space: `${space2.id}`,
          subnet: `${subnet2.id}`,
        },
      ];
      expect(
        createInterfaceConstraints(
          [interface1, interface2],
          [space1, space2],
          [subnet1, subnet2]
        )
      ).toEqual(
        `eth0:ip=${interface1.ipAddress},space=${space1.name},subnet_cidr=${subnet1.cidr};` +
          `eth1:ip=${interface2.ipAddress},space=${space2.name},subnet_cidr=${subnet2.cidr}`
      );
    });
  });

  describe("createStorageConstraints", () => {
    it("returns an empty string if no disks are given", () => {
      expect(createStorageConstraints()).toEqual("");
      expect(createStorageConstraints([])).toEqual("");
    });

    it("correctly returns storage constraint for pod compose action", () => {
      const [pool1, pool2] = [
        factory.podStoragePool({ name: "pool-1" }),
        factory.podStoragePool({ name: "pool-2" }),
      ];
      const [bootDisk, otherDisk] = [
        { id: 1, location: pool1.name, size: 16, tags: ["tag1", "tag2"] },
        { id: 2, location: pool2.name, size: 32, tags: ["tag3"] },
      ];

      expect(
        createStorageConstraints([otherDisk, bootDisk], bootDisk.id)
      ).toEqual(
        `${bootDisk.id}:${bootDisk.size}(${
          bootDisk.location
        },${bootDisk.tags.join(",")}),${otherDisk.id}:${otherDisk.size}(${
          otherDisk.location
        },${otherDisk.tags.join(",")})`
      );
    });
  });

  describe("getDefaultPoolLocation", () => {
    it("correctly returns default pool name", () => {
      const [defaultPool, otherPool] = [
        factory.podStoragePool(),
        factory.podStoragePool(),
      ];
      const pod = factory.podDetails({
        default_storage_pool: defaultPool.id,
        storage_pools: [defaultPool, otherPool],
        type: PodType.LXD,
      });
      expect(getDefaultPoolLocation(pod)).toBe(defaultPool.name);
    });
  });
});
