import { PodType } from "./constants";
import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

describe("pod reducer", () => {
  it("returns the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual({
      active: null,
      errors: null,
      items: [],
      loaded: false,
      loading: false,
      projects: {},
      saved: false,
      saving: false,
      statuses: {},
    });
  });

  it("reduces fetch", () => {
    const podState = factory.podState();

    expect(reducers(podState, actions.fetch())).toEqual(factory.podState());
  });

  it("reduces fetchStart", () => {
    const podState = factory.podState({ loading: false });

    expect(reducers(podState, actions.fetchStart())).toEqual(
      factory.podState({
        loading: true,
      })
    );
  });

  it("reduces fetchSuccess", () => {
    const pods = [factory.pod()];
    const podState = factory.podState({
      items: [],
      loaded: false,
      loading: true,
    });
    expect(reducers(podState, actions.fetchSuccess(pods))).toEqual(
      factory.podState({
        loading: false,
        loaded: true,
        statuses: { 1: factory.podStatus() },
        items: pods,
      })
    );
  });

  it("does not override the active pod when reducing fetchSuccess", () => {
    const activePod = factory.podDetails();
    const podState = factory.podState({
      active: activePod.id,
      items: [activePod],
      statuses: {
        [activePod.id]: factory.podStatus({ refreshing: true }),
      },
    });
    const pods = [
      // The fetch response will include the non-details version of the pod.
      factory.pod({ id: activePod.id }),
      factory.pod(),
      factory.pod(),
    ];
    expect(reducers(podState, actions.fetchSuccess(pods))).toEqual(
      factory.podState({
        active: activePod.id,
        loading: false,
        loaded: true,
        statuses: {
          [activePod.id]: factory.podStatus({ refreshing: true }),
          [pods[1].id]: factory.podStatus(),
          [pods[2].id]: factory.podStatus(),
        },
        items: [activePod, pods[1], pods[2]],
      })
    );
  });

  it("reduces fetchError", () => {
    const podState = factory.podState({
      errors: null,
      loaded: false,
      loading: true,
    });

    expect(
      reducers(podState, actions.fetchError("Could not fetch pods"))
    ).toEqual(
      factory.podState({
        errors: "Could not fetch pods",
        loaded: false,
        loading: false,
      })
    );
  });

  it("reduces getStart", () => {
    const podState = factory.podState({ items: [], loading: false });

    expect(reducers(podState, actions.getStart())).toEqual(
      factory.podState({ loading: true })
    );
  });

  it("reduces getSuccess", () => {
    const newPod = factory.podDetails();
    const podState = factory.podState({
      items: [],
      loading: true,
    });

    expect(reducers(podState, actions.getSuccess(newPod))).toEqual(
      factory.podState({
        items: [newPod],
        loading: false,
        statuses: { [newPod.id]: factory.podStatus() },
      })
    );
  });

  it("reduces getError", () => {
    const podState = factory.podState({ loading: true });

    expect(reducers(podState, actions.getError("Could not get pod"))).toEqual(
      factory.podState({
        errors: "Could not get pod",
        loading: false,
      })
    );
  });

  it("reduces createStart", () => {
    const podState = factory.podState({ saved: true, saving: false });

    expect(reducers(podState, actions.createStart())).toEqual(
      factory.podState({
        saved: false,
        saving: true,
      })
    );
  });

  it("reduces createError", () => {
    const podState = factory.podState({ errors: null, saving: true });

    expect(
      reducers(
        podState,
        actions.createError({ name: "Pod name already exists" })
      )
    ).toEqual(
      factory.podState({
        errors: { name: "Pod name already exists" },
        saving: false,
      })
    );
  });

  it("updates pods on createNotify", () => {
    const pods = [factory.pod({ id: 1 })];
    const newPod = factory.pod({ id: 2 });
    const podState = factory.podState({
      items: pods,
      statuses: {
        1: factory.podStatus(),
      },
    });

    expect(reducers(podState, actions.createNotify(newPod))).toEqual(
      factory.podState({
        items: [...pods, newPod],
        statuses: { 1: factory.podStatus(), 2: factory.podStatus() },
      })
    );
  });

  it("reduces composeStart", () => {
    const pods = [factory.pod({ id: 1 })];
    const podState = factory.podState({
      items: pods,
      statuses: {
        1: factory.podStatus({ composing: false }),
      },
    });

    expect(reducers(podState, actions.composeStart({ item: pods[0] }))).toEqual(
      factory.podState({
        items: pods,
        statuses: { 1: factory.podStatus({ composing: true }) },
      })
    );
  });

  it("reduces composeSuccess", () => {
    const pods = [factory.pod({ id: 1 })];
    const podState = factory.podState({
      items: pods,
      statuses: {
        1: factory.podStatus({ composing: true }),
      },
    });

    expect(
      reducers(podState, actions.composeSuccess({ item: pods[0] }))
    ).toEqual(
      factory.podState({
        items: pods,
        statuses: { 1: factory.podStatus({ composing: false }) },
      })
    );
  });

  it("reduces composeError", () => {
    const pods = [factory.pod({ id: 1 })];
    const podState = factory.podState({
      errors: null,
      items: pods,
      statuses: {
        1: factory.podStatus({ composing: true }),
      },
    });

    expect(
      reducers(
        podState,
        actions.composeError({ item: pods[0], payload: "You dun goofed" })
      )
    ).toEqual(
      factory.podState({
        errors: "You dun goofed",
        items: pods,
        statuses: { 1: factory.podStatus({ composing: false }) },
      })
    );
  });

  it("reduces deleteStart", () => {
    const pods = [factory.pod({ id: 1 })];
    const podState = factory.podState({
      items: pods,
      statuses: { 1: factory.podStatus({ deleting: false }) },
    });

    expect(reducers(podState, actions.deleteStart({ item: pods[0] }))).toEqual(
      factory.podState({
        items: pods,
        statuses: { 1: factory.podStatus({ deleting: true }) },
      })
    );
  });

  it("reduces deleteSuccess", () => {
    const pods = [factory.pod({ id: 1 })];
    const podState = factory.podState({
      items: pods,
      statuses: { 1: factory.podStatus({ deleting: true }) },
    });

    expect(
      reducers(podState, actions.deleteSuccess({ item: pods[0] }))
    ).toEqual(
      factory.podState({
        items: pods,
        statuses: { 1: factory.podStatus({ deleting: false }) },
      })
    );
  });

  it("reduces deleteError", () => {
    const pods = [factory.pod({ id: 1 })];
    const podState = factory.podState({
      errors: null,
      items: pods,
      statuses: { 1: factory.podStatus({ deleting: true }) },
    });

    expect(
      reducers(
        podState,
        actions.deleteError({ item: pods[0], payload: "Pod cannot be deleted" })
      )
    ).toEqual(
      factory.podState({
        errors: "Pod cannot be deleted",
        items: pods,
        statuses: { 1: factory.podStatus({ deleting: false }) },
      })
    );
  });

  it("reduces deleteNotify", () => {
    const pods = [factory.pod({ id: 1 }), factory.pod({ id: 2 })];
    const podState = factory.podState({
      items: pods,
      statuses: {
        1: factory.podStatus({ deleting: true }),
        2: factory.podStatus(),
      },
    });

    expect(reducers(podState, actions.deleteNotify(1))).toEqual(
      factory.podState({
        items: [pods[1]],
        statuses: { 2: factory.podStatus() },
      })
    );
  });

  it("reduces refreshStart", () => {
    const pods = [factory.pod({ id: 1 })];
    const podState = factory.podState({
      items: pods,
      statuses: {
        1: factory.podStatus({ refreshing: false }),
      },
    });

    expect(reducers(podState, actions.refreshStart({ item: pods[0] }))).toEqual(
      factory.podState({
        items: pods,
        statuses: { 1: factory.podStatus({ refreshing: true }) },
      })
    );
  });

  it("reduces refreshSuccess", () => {
    const pods = [factory.pod({ id: 1, cpu_speed: 100 })];
    const updatedPod = factory.pod({ id: 1, cpu_speed: 100 });
    const podState = factory.podState({
      items: pods,
      statuses: {
        1: factory.podStatus({ refreshing: true }),
      },
    });

    expect(
      reducers(
        podState,
        actions.refreshSuccess({ item: pods[0], payload: updatedPod })
      )
    ).toEqual(
      factory.podState({
        items: [updatedPod],
        statuses: { 1: factory.podStatus({ refreshing: false }) },
      })
    );
  });

  it("reduces refreshError", () => {
    const pods = [factory.pod({ id: 1, cpu_speed: 100 })];
    const podState = factory.podState({
      errors: null,
      items: pods,
      statuses: {
        1: factory.podStatus({ refreshing: true }),
      },
    });

    expect(
      reducers(
        podState,
        actions.refreshError({ item: pods[0], payload: "You dun goofed" })
      )
    ).toEqual(
      factory.podState({
        errors: "You dun goofed",
        items: pods,
        statuses: { 1: factory.podStatus({ refreshing: false }) },
      })
    );
  });

  it("reduces setActiveError", () => {
    const podState = factory.podState({
      active: 1,
      errors: null,
    });

    expect(
      reducers(
        podState,
        actions.setActiveError("Pod with this id does not exist")
      )
    ).toEqual(
      factory.podState({
        active: null,
        errors: "Pod with this id does not exist",
      })
    );
  });

  it("reduces setActiveSuccess", () => {
    const podState = factory.podState({
      active: null,
    });

    expect(
      reducers(podState, actions.setActiveSuccess(factory.pod({ id: 101 })))
    ).toEqual(
      factory.podState({
        active: 101,
      })
    );
  });

  it("reduces getProjectsSuccess", () => {
    const serverAddress = "192.168.1.1";
    const newProjects = [factory.podProject()];
    const podState = factory.podState({
      items: [],
      projects: {},
    });

    expect(
      reducers(
        podState,
        actions.getProjectsSuccess(
          { power_address: serverAddress, type: PodType.LXD },
          newProjects
        )
      )
    ).toEqual(
      factory.podState({
        projects: { [serverAddress]: newProjects },
      })
    );
  });

  it("reduces getProjectsError", () => {
    const podState = factory.podState();

    expect(
      reducers(podState, actions.getProjectsError("Could not get projects"))
    ).toEqual(
      factory.podState({
        errors: "Could not get projects",
        loading: false,
      })
    );
  });

  it("reduces clearProjects", () => {
    const podState = factory.podState({
      projects: {
        "192.168.1.1": [factory.podProject()],
      },
    });

    expect(reducers(podState, actions.clearProjects())).toEqual(
      factory.podState({
        projects: {},
      })
    );
  });

  it("reduces pollLxdServerSuccess", () => {
    const serverAddress = "192.168.1.1";
    const newProjects = [factory.podProject()];
    const podState = factory.podState({
      errors: "it's not working",
      items: [],
      projects: {},
    });

    expect(
      reducers(
        podState,
        actions.pollLxdServerSuccess(
          { power_address: serverAddress, type: PodType.LXD },
          newProjects
        )
      )
    ).toEqual(
      factory.podState({
        errors: null,
        projects: { [serverAddress]: newProjects },
      })
    );
  });

  it("reduces pollLxdServerError", () => {
    const podState = factory.podState({
      errors: null,
    });

    expect(reducers(podState, actions.pollLxdServerError("Error!"))).toEqual(
      factory.podState({
        errors: "Error!",
      })
    );
  });
});
