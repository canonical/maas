import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

describe("subnet reducer", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual(factory.subnetState());
  });

  describe("fetch", () => {
    it("reduces fetchStart", () => {
      const initialState = factory.subnetState({ loading: false });

      expect(reducers(initialState, actions.fetchStart())).toEqual(
        factory.subnetState({ loading: true })
      );
    });

    it("reduces fetchSuccess", () => {
      const initialState = factory.subnetState({
        items: [],
        loaded: false,
        loading: true,
      });
      const subnets = [factory.subnet({ id: 1 }), factory.subnet({ id: 2 })];

      expect(reducers(initialState, actions.fetchSuccess(subnets))).toEqual(
        factory.subnetState({
          items: subnets,
          loaded: true,
          loading: false,
          statuses: factory.subnetStatuses({
            1: factory.subnetStatus(),
            2: factory.subnetStatus(),
          }),
        })
      );
    });

    it("reduces fetchError", () => {
      const initialState = factory.subnetState({
        errors: null,
        loading: true,
      });

      expect(
        reducers(initialState, actions.fetchError("Could not fetch subnets"))
      ).toEqual(
        factory.subnetState({
          errors: "Could not fetch subnets",
          eventErrors: [
            factory.subnetEventError({
              error: "Could not fetch subnets",
              event: "fetch",
              id: null,
            }),
          ],
          loading: false,
        })
      );
    });
  });

  describe("create", () => {
    it("reduces createStart", () => {
      const initialState = factory.subnetState({ saving: false });

      expect(reducers(initialState, actions.createStart())).toEqual(
        factory.subnetState({ saving: true })
      );
    });

    it("reduces createSuccess", () => {
      const initialState = factory.subnetState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.createSuccess())).toEqual(
        factory.subnetState({ saved: true, saving: false })
      );
    });

    it("reduces createNotify", () => {
      const initialState = factory.subnetState({
        items: [factory.subnet()],
      });
      const newSubnet = factory.subnet({ id: 1 });

      expect(reducers(initialState, actions.createNotify(newSubnet))).toEqual(
        factory.subnetState({
          items: [...initialState.items, newSubnet],
          statuses: factory.subnetStatuses({
            1: factory.subnetStatus(),
          }),
        })
      );
    });

    it("reduces createError", () => {
      const initialState = factory.subnetState({
        errors: null,
        saving: true,
      });

      expect(
        reducers(initialState, actions.createError("Could not create subnet"))
      ).toEqual(
        factory.subnetState({
          errors: "Could not create subnet",
          eventErrors: [
            factory.subnetEventError({
              error: "Could not create subnet",
              event: "create",
              id: null,
            }),
          ],
          saving: false,
        })
      );
    });
  });

  describe("update", () => {
    it("reduces updateStart", () => {
      const initialState = factory.subnetState({ saving: false });

      expect(reducers(initialState, actions.updateStart())).toEqual(
        factory.subnetState({ saving: true })
      );
    });

    it("reduces updateSuccess", () => {
      const initialState = factory.subnetState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.updateSuccess())).toEqual(
        factory.subnetState({ saved: true, saving: false })
      );
    });

    it("reduces updateNotify", () => {
      const initialState = factory.subnetState({
        items: [factory.subnet()],
      });
      const updatedSubnet = factory.subnet({
        id: initialState.items[0].id,
        name: "updated-reducers",
      });

      expect(
        reducers(initialState, actions.updateNotify(updatedSubnet))
      ).toEqual(factory.subnetState({ items: [updatedSubnet] }));
    });

    it("reduces updateError", () => {
      const initialState = factory.subnetState({
        errors: null,
        saving: true,
      });

      expect(
        reducers(initialState, actions.updateError("Could not update subnet"))
      ).toEqual(
        factory.subnetState({
          errors: "Could not update subnet",
          eventErrors: [
            factory.subnetEventError({
              error: "Could not update subnet",
              event: "update",
              id: null,
            }),
          ],
          saving: false,
        })
      );
    });
  });

  describe("delete", () => {
    it("reduces deleteStart", () => {
      const initialState = factory.subnetState({ saving: false });

      expect(reducers(initialState, actions.deleteStart())).toEqual(
        factory.subnetState({ saving: true })
      );
    });

    it("reduces deleteSuccess", () => {
      const initialState = factory.subnetState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.deleteSuccess())).toEqual(
        factory.subnetState({ saved: true, saving: false })
      );
    });

    it("reduces deleteNotify", () => {
      const [deleteSubnet, keepSubnet] = [factory.subnet(), factory.subnet()];
      const initialState = factory.subnetState({
        items: [deleteSubnet, keepSubnet],
      });

      expect(
        reducers(initialState, actions.deleteNotify(deleteSubnet.id))
      ).toEqual(factory.subnetState({ items: [keepSubnet] }));
    });

    it("reduces deleteError", () => {
      const initialState = factory.subnetState({
        errors: null,
        saving: true,
      });

      expect(
        reducers(initialState, actions.deleteError("Could not delete subnet"))
      ).toEqual(
        factory.subnetState({
          errors: "Could not delete subnet",
          eventErrors: [
            factory.subnetEventError({
              error: "Could not delete subnet",
              event: "delete",
              id: null,
            }),
          ],
          saving: false,
        })
      );
    });
  });

  describe("get", () => {
    it("reduces getStart", () => {
      const initialState = factory.subnetState({ loading: false });

      expect(reducers(initialState, actions.getStart())).toEqual(
        factory.subnetState({ loading: true })
      );
    });

    it("reduces getError", () => {
      const initialState = factory.subnetState({ errors: null, loading: true });

      expect(
        reducers(initialState, actions.getError({ id: "id was not supplied" }))
      ).toEqual(
        factory.subnetState({
          errors: { id: "id was not supplied" },
          loading: false,
        })
      );
    });

    it("reduces getSuccess when subnet already exists in state", () => {
      const initialState = factory.subnetState({
        items: [factory.subnet({ id: 0, name: "subnet-1" })],
        loading: true,
      });
      const updatedSubnet = factory.subnet({
        id: 0,
        name: "subnet-1-new",
      });

      expect(reducers(initialState, actions.getSuccess(updatedSubnet))).toEqual(
        factory.subnetState({
          items: [updatedSubnet],
          loading: false,
        })
      );
    });

    it("reduces getSuccess when subnet does not exist yet in state", () => {
      const initialState = factory.subnetState({
        items: [factory.subnet({ id: 0 })],
        loading: true,
        statuses: factory.subnetStatuses({ 0: factory.subnetStatus() }),
      });
      const newSubnet = factory.subnet({ id: 1 });

      expect(reducers(initialState, actions.getSuccess(newSubnet))).toEqual(
        factory.subnetState({
          items: [...initialState.items, newSubnet],
          loading: false,
          statuses: { ...initialState.statuses, 1: factory.subnetStatus() },
        })
      );
    });
  });

  describe("setActive", () => {
    it("reduces setActiveSuccess", () => {
      const initialState = factory.subnetState({ active: null });

      expect(
        reducers(
          initialState,
          actions.setActiveSuccess(factory.subnet({ id: 0 }))
        )
      ).toEqual(factory.subnetState({ active: 0 }));
    });

    it("reduces setActiveError", () => {
      const initialState = factory.subnetState({
        active: 0,
        errors: null,
      });

      expect(
        reducers(initialState, actions.setActiveError("Subnet does not exist"))
      ).toEqual(
        factory.subnetState({
          active: null,
          errors: "Subnet does not exist",
        })
      );
    });
  });

  describe("scan", () => {
    it("reduces scanStart", () => {
      const initialState = factory.subnetState({
        statuses: factory.subnetStatuses({
          0: factory.subnetStatus({ scanning: false }),
        }),
      });

      expect(
        reducers(initialState, actions.scanStart({ item: { id: 0 } }))
      ).toEqual(
        factory.subnetState({
          statuses: factory.subnetStatuses({
            0: factory.subnetStatus({ scanning: true }),
          }),
        })
      );
    });

    it("reduces scanSuccess when scan successfully started", () => {
      const initialState = factory.subnetState({
        statuses: factory.subnetStatuses({
          0: factory.subnetStatus({ scanning: true }),
        }),
      });
      const scanResult = factory.subnetScanResult({
        result: "All good",
        scan_started_on: [factory.subnetBMCNode()],
      });

      expect(
        reducers(
          initialState,
          actions.scanSuccess({ item: { id: 0 }, payload: scanResult })
        )
      ).toEqual(
        factory.subnetState({
          statuses: factory.subnetStatuses({
            0: factory.subnetStatus({ scanning: false }),
          }),
        })
      );
    });

    it("reduces scanSuccess when scan was not successfully started", () => {
      const initialState = factory.subnetState({
        statuses: factory.subnetStatuses({
          0: factory.subnetStatus({ scanning: true }),
        }),
      });
      const scanResult = factory.subnetScanResult({
        result: "No good",
        scan_started_on: [],
      });

      expect(
        reducers(
          initialState,
          actions.scanSuccess({ item: { id: 0 }, payload: scanResult })
        )
      ).toEqual(
        factory.subnetState({
          errors: "No good",
          eventErrors: [
            factory.subnetEventError({
              error: "No good",
              event: "scan",
              id: 0,
            }),
          ],
          statuses: factory.subnetStatuses({
            0: factory.subnetStatus({ scanning: false }),
          }),
        })
      );
    });

    it("reduces scanError", () => {
      const initialState = factory.subnetState({
        statuses: factory.subnetStatuses({
          0: factory.subnetStatus({ scanning: true }),
        }),
      });

      expect(
        reducers(
          initialState,
          actions.scanError({
            error: true,
            item: { id: 0 },
            payload: "You broke it",
          })
        )
      ).toEqual(
        factory.subnetState({
          errors: "You broke it",
          eventErrors: [
            factory.subnetEventError({
              error: "You broke it",
              event: "scan",
              id: 0,
            }),
          ],
          statuses: factory.subnetStatuses({
            0: factory.subnetStatus({ scanning: false }),
          }),
        })
      );
    });
  });
});
