import pod from "./selectors";

import { PodType } from "@/app/store/pod/constants";
import * as factory from "@/testing/factories";

describe("pod selectors", () => {
  it("can get all items", () => {
    const items = [factory.pod(), factory.pod()];
    const state = factory.rootState({
      pod: factory.podState({
        items,
      }),
    });
    expect(pod.all(state)).toEqual(items);
  });

  it("can get all projects", () => {
    const projects = {
      "172.0.0.1": [factory.podProject()],
      "192.168.1.1": [factory.podProject()],
    };
    const state = factory.rootState({
      pod: factory.podState({
        projects,
      }),
    });
    expect(pod.projects(state)).toEqual(projects);
  });

  it("can get all KVMs that MAAS supports", () => {
    const items = [
      factory.pod({ type: PodType.VIRSH }),
      factory.pod({ type: PodType.LXD }),
    ];
    const state = factory.rootState({
      pod: factory.podState({
        items,
      }),
    });
    expect(pod.kvms(state)).toStrictEqual([items[0], items[1]]);
  });

  it("can get all LXD pods", () => {
    const items = [
      factory.pod({ type: PodType.VIRSH }),
      factory.pod({ type: PodType.LXD }),
    ];
    const state = factory.rootState({
      pod: factory.podState({
        items,
      }),
    });
    expect(pod.lxd(state)).toStrictEqual([items[1]]);
  });

  it("can get all LXD pods that aren't cluster hosts", () => {
    const items = [
      factory.pod({ type: PodType.VIRSH, name: "virsh host" }),
      factory.pod({ type: PodType.LXD, name: "cluster host", cluster: 0 }),
      factory.pod({ type: PodType.LXD, name: "single host 1" }),
      factory.pod({ type: PodType.LXD, name: "single host 2" }),
    ];
    const state = factory.rootState({
      pod: factory.podState({
        items,
      }),
    });
    expect(pod.lxdSingleHosts(state)).toStrictEqual([items[2], items[3]]);
  });

  it("can get all virsh pods", () => {
    const items = [
      factory.pod({ type: PodType.VIRSH }),
      factory.pod({ type: PodType.LXD }),
    ];
    const state = factory.rootState({
      pod: factory.podState({
        items,
      }),
    });
    expect(pod.virsh(state)).toStrictEqual([items[0]]);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      pod: factory.podState({
        loading: true,
      }),
    });
    expect(pod.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      pod: factory.podState({
        loaded: true,
      }),
    });
    expect(pod.loaded(state)).toEqual(true);
  });

  it("can get the saving state", () => {
    const state = factory.rootState({
      pod: factory.podState({
        saving: true,
      }),
    });
    expect(pod.saving(state)).toEqual(true);
  });

  it("can get the saved state", () => {
    const state = factory.rootState({
      pod: factory.podState({
        saved: true,
      }),
    });
    expect(pod.saved(state)).toEqual(true);
  });

  it("can get the active pod id", () => {
    const state = factory.rootState({
      pod: factory.podState({
        active: 1,
      }),
    });
    expect(pod.activeID(state)).toEqual(1);
  });

  it("can get the active pod", () => {
    const activePod = factory.pod();
    const state = factory.rootState({
      pod: factory.podState({
        active: activePod.id,
        items: [activePod],
      }),
    });
    expect(pod.active(state)).toEqual(activePod);
  });

  it("can get the errors state", () => {
    const state = factory.rootState({
      pod: factory.podState({
        errors: "Data is incorrect",
      }),
    });
    expect(pod.errors(state)).toStrictEqual("Data is incorrect");
  });

  it("can get a pod by id", () => {
    const items = [factory.pod({ id: 111 }), factory.pod({ id: 222 })];
    const state = factory.rootState({
      pod: factory.podState({
        items,
      }),
    });
    expect(pod.getById(state, 222)).toStrictEqual(items[1]);
  });

  it("can get a pod's host machine", () => {
    const items = [factory.pod({ host: "abc123" })];
    const machineItems = [
      factory.machine({ system_id: "abc123" }),
      factory.machine(),
    ];
    const state = factory.rootState({
      controller: factory.controllerState({
        items: [factory.controller()],
      }),
      machine: factory.machineState({
        items: machineItems,
      }),
      pod: factory.podState({
        items,
      }),
    });
    expect(pod.getHost(state, items[0])).toStrictEqual(machineItems[0]);
  });

  it("can get a pod's host controller", () => {
    const items = [factory.pod({ host: "abc123" })];
    const controllerItems = [
      factory.controller({ system_id: "abc123" }),
      factory.controller(),
    ];
    const state = factory.rootState({
      controller: factory.controllerState({
        items: controllerItems,
      }),
      machine: factory.machineState({
        items: [factory.machine()],
      }),
      pod: factory.podState({
        items,
      }),
    });
    expect(pod.getHost(state, items[0])).toStrictEqual(controllerItems[0]);
  });

  it("can get all pod hosts", () => {
    const items = [
      factory.pod({ host: "aaaaaa" }),
      factory.pod({ host: "bbbbbb" }),
      factory.pod({ host: "cccccc" }),
    ];
    const controllerItems = [
      factory.controller({ system_id: "aaaaaa" }),
      factory.controller({ system_id: "bbbbbb" }),
    ];
    const machineItems = [
      factory.machine({ system_id: "cccccc" }),
      factory.machine({ system_id: "dddddd" }),
    ];
    const state = factory.rootState({
      controller: factory.controllerState({
        items: controllerItems,
      }),
      machine: factory.machineState({
        items: machineItems,
      }),
      pod: factory.podState({
        items,
      }),
    });
    expect(pod.getAllHosts(state)).toStrictEqual([
      controllerItems[0],
      controllerItems[1],
      machineItems[0],
    ]);
  });

  it("can group LXD pods by LXD server address", () => {
    const items = [
      factory.pod({ type: PodType.VIRSH }),
      factory.pod({
        power_parameters: factory.podPowerParameters({
          power_address: "172.0.0.1",
        }),
        type: PodType.LXD,
      }),
      factory.pod({
        power_parameters: factory.podPowerParameters({
          power_address: "172.0.0.1",
        }),
        type: PodType.LXD,
      }),
      factory.pod({
        power_parameters: factory.podPowerParameters({
          power_address: "192.168.0.1:8000",
        }),
        type: PodType.LXD,
      }),
      factory.pod({
        power_parameters: factory.podPowerParameters({
          power_address: "192.168.0.1:9000",
        }),
        type: PodType.LXD,
      }),
    ];
    const state = factory.rootState({
      pod: factory.podState({
        items,
      }),
    });
    expect(pod.groupByLxdServer(state)).toStrictEqual([
      {
        address: "172.0.0.1",
        pods: [items[1], items[2]],
      },
      {
        address: "192.168.0.1:8000",
        pods: [items[3]],
      },
      {
        address: "192.168.0.1:9000",
        pods: [items[4]],
      },
    ]);
  });

  it("can get LXD pods by LXD server address", () => {
    const items = [
      factory.pod({ type: PodType.VIRSH }),
      factory.pod({
        power_parameters: factory.podPowerParameters({
          power_address: "172.0.0.1",
        }),
        type: PodType.LXD,
      }),
      factory.pod({
        power_parameters: factory.podPowerParameters({
          power_address: "172.0.0.1",
        }),
        type: PodType.LXD,
      }),
      factory.pod({
        power_parameters: factory.podPowerParameters({
          power_address: "192.168.0.1:8000",
        }),
        type: PodType.LXD,
      }),
      factory.pod({
        power_parameters: factory.podPowerParameters({
          power_address: "192.168.0.1:9000",
        }),
        type: PodType.LXD,
      }),
    ];
    const state = factory.rootState({
      pod: factory.podState({
        items,
      }),
    });
    expect(pod.getByLxdServer(state, "172.0.0.1")).toStrictEqual([
      items[1],
      items[2],
    ]);
  });

  it("can get projects by LXD server address", () => {
    const projects = [factory.podProject(), factory.podProject()];
    const state = factory.rootState({
      pod: factory.podState({
        projects: {
          "172.0.0.1": projects,
        },
      }),
    });
    expect(pod.getProjectsByLxdServer(state, "172.0.0.1")).toEqual(projects);
  });

  it("can get a specific VM resource of a pod", () => {
    const [thisVmResource, otherVmResource] = [
      factory.podVM({ system_id: "abc123" }),
      factory.podVM({ system_id: "def456" }),
    ];
    const state = factory.rootState({
      pod: factory.podState({
        items: [
          factory.pod({
            id: 1,
            resources: factory.podResources({
              vms: [thisVmResource, otherVmResource],
            }),
          }),
        ],
      }),
    });
    expect(pod.getVmResource(state, 1, "abc123")).toEqual(thisVmResource);
  });

  it("can get the LXD hosts that are in a given cluster", () => {
    const inCluster = [
      factory.pod({ type: PodType.LXD, cluster: 0 }),
      factory.pod({ type: PodType.LXD, cluster: 0 }),
    ];
    const notInCluster = [
      factory.pod({ type: PodType.LXD }),
      factory.pod({ type: PodType.VIRSH }),
    ];

    const state = factory.rootState({
      pod: factory.podState({
        items: [...inCluster, ...notInCluster],
      }),
    });
    expect(pod.lxdHostsInClusterById(state, 0)).toEqual(inCluster);
  });
});
