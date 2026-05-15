import { subnetActions } from "@/app/store/subnet";
import reducers, { vlanActions } from "@/app/store/vlan";
import * as factory from "@/testing/factories";

describe("vlan reducer", () => {
  describe("initial", () => {
    it("returns the initial state", () => {
      const initialState = undefined;

      expect(reducers(initialState, { type: "" })).toEqual({
        active: null,
        errors: null,
        eventErrors: [],
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
        statuses: {},
      });
    });
  });

  describe("fetch", () => {
    it("reduces fetchStart", () => {
      const initialState = factory.vlanState({ loading: false });

      expect(reducers(initialState, vlanActions.fetchStart())).toEqual(
        factory.vlanState({ loading: true })
      );
    });

    it("reduces fetchSuccess", () => {
      const initialState = factory.vlanState({
        items: [],
        loaded: false,
        loading: true,
      });
      const vlans = [factory.vlan({ id: 1 }), factory.vlan({ id: 2 })];

      expect(reducers(initialState, vlanActions.fetchSuccess(vlans))).toEqual(
        factory.vlanState({
          items: vlans,
          loaded: true,
          loading: false,
          statuses: factory.vlanStatuses({
            1: factory.vlanStatus(),
            2: factory.vlanStatus(),
          }),
        })
      );
    });

    it("reduces fetchError", () => {
      const initialState = factory.vlanState({ errors: "", loading: true });

      expect(
        reducers(initialState, vlanActions.fetchError("Could not fetch vlans"))
      ).toEqual(
        factory.vlanState({
          errors: "Could not fetch vlans",
          eventErrors: [
            factory.vlanEventError({
              error: "Could not fetch vlans",
              event: "fetch",
              id: null,
            }),
          ],
        })
      );
    });
  });

  describe("create", () => {
    it("reduces createStart", () => {
      const initialState = factory.vlanState({ saving: false });

      expect(reducers(initialState, vlanActions.createStart())).toEqual(
        factory.vlanState({ saving: true })
      );
    });

    it("reduces createSuccess", () => {
      const initialState = factory.vlanState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, vlanActions.createSuccess())).toEqual(
        factory.vlanState({ errors: null, saved: true, saving: false })
      );
    });

    it("reduces createNotify", () => {
      const initialState = factory.vlanState({
        items: [factory.vlan()],
      });
      const newVLAN = factory.vlan({ id: 1 });

      expect(reducers(initialState, vlanActions.createNotify(newVLAN))).toEqual(
        factory.vlanState({
          items: [...initialState.items, newVLAN],
          statuses: factory.vlanStatuses({ 1: factory.vlanStatus() }),
        })
      );
    });

    it("reduces createError", () => {
      const initialState = factory.vlanState({ errors: "", saving: true });

      expect(
        reducers(initialState, vlanActions.createError("Could not create vlan"))
      ).toEqual(
        factory.vlanState({
          errors: "Could not create vlan",
          eventErrors: [
            factory.vlanEventError({
              error: "Could not create vlan",
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
      const initialState = factory.vlanState({ saving: false });

      expect(reducers(initialState, vlanActions.updateStart())).toEqual(
        factory.vlanState({ saving: true })
      );
    });

    it("reduces updateSuccess", () => {
      const initialState = factory.vlanState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, vlanActions.updateSuccess())).toEqual(
        factory.vlanState({ errors: null, saved: true, saving: false })
      );
    });

    it("reduces updateNotify ", () => {
      const initialState = factory.vlanState({
        items: [factory.vlan()],
      });
      const updatedVLAN = factory.vlan({
        id: initialState.items[0].id,
        name: "updated-vlan",
      });

      expect(
        reducers(initialState, vlanActions.updateNotify(updatedVLAN))
      ).toEqual(factory.vlanState({ items: [updatedVLAN] }));
    });

    it("reduces updateError", () => {
      const initialState = factory.vlanState({ errors: "", saving: true });

      expect(
        reducers(initialState, vlanActions.updateError("Could not update vlan"))
      ).toEqual(
        factory.vlanState({
          errors: "Could not update vlan",
          eventErrors: [
            factory.vlanEventError({
              error: "Could not update vlan",
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
      const initialState = factory.vlanState({ saving: false });

      expect(reducers(initialState, vlanActions.deleteStart())).toEqual(
        factory.vlanState({ saving: true })
      );
    });

    it("reduces deleteSuccess", () => {
      const initialState = factory.vlanState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, vlanActions.deleteSuccess())).toEqual(
        factory.vlanState({ errors: null, saved: true, saving: false })
      );
    });

    it("reduces deleteNotify", () => {
      const [deleteVLAN, keepVLAN] = [factory.vlan(), factory.vlan()];
      const initialState = factory.vlanState({
        items: [deleteVLAN, keepVLAN],
      });

      expect(
        reducers(initialState, vlanActions.deleteNotify(deleteVLAN.id))
      ).toEqual(factory.vlanState({ items: [keepVLAN] }));
    });

    it("reduces deleteError", () => {
      const initialState = factory.vlanState({ errors: "", saving: true });

      expect(
        reducers(initialState, vlanActions.deleteError("Could not delete vlan"))
      ).toEqual(
        factory.vlanState({
          errors: "Could not delete vlan",
          eventErrors: [
            factory.vlanEventError({
              error: "Could not delete vlan",
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
      const initialState = factory.vlanState({ loading: false });

      expect(reducers(initialState, vlanActions.getStart())).toEqual(
        factory.vlanState({ loading: true })
      );
    });

    it("reduces getError", () => {
      const initialState = factory.vlanState({ errors: null, loading: true });

      expect(
        reducers(
          initialState,
          vlanActions.getError({ id: "id was not supplied" })
        )
      ).toEqual(
        factory.vlanState({
          errors: { id: "id was not supplied" },
          loading: false,
        })
      );
    });

    it("reduces getSuccess when vlan already exists in state", () => {
      const initialState = factory.vlanState({
        items: [factory.vlan({ id: 0, name: "vlan-1" })],
        loading: true,
      });
      const updatedVLAN = factory.vlan({
        id: 0,
        name: "vlan-1-new",
      });

      expect(
        reducers(initialState, vlanActions.getSuccess(updatedVLAN))
      ).toEqual(
        factory.vlanState({
          items: [updatedVLAN],
          loading: false,
        })
      );
    });

    it("reduces getSuccess when vlan does not exist yet in state", () => {
      const initialState = factory.vlanState({
        items: [factory.vlan({ id: 0 })],
        loading: true,
      });
      const newVLAN = factory.vlan({ id: 1 });

      expect(reducers(initialState, vlanActions.getSuccess(newVLAN))).toEqual(
        factory.vlanState({
          items: [...initialState.items, newVLAN],
          loading: false,
          statuses: factory.vlanStatuses({
            1: factory.vlanStatus(),
          }),
        })
      );
    });
  });

  describe("setActive", () => {
    it("reduces setActiveSuccess", () => {
      const initialState = factory.vlanState({ active: null });

      expect(
        reducers(
          initialState,
          vlanActions.setActiveSuccess(factory.vlan({ id: 0 }))
        )
      ).toEqual(factory.vlanState({ active: 0 }));
    });

    it("reduces setActiveError", () => {
      const initialState = factory.vlanState({
        active: 0,
        errors: null,
      });

      expect(
        reducers(
          initialState,
          vlanActions.setActiveError("VLAN does not exist")
        )
      ).toEqual(
        factory.vlanState({
          active: null,
          errors: "VLAN does not exist",
        })
      );
    });
  });

  describe("configureDHCP", () => {
    it("reduces configureDHCPStart", () => {
      const initialState = factory.vlanState({
        statuses: factory.vlanStatuses({
          0: factory.vlanStatus({ configuringDHCP: false }),
        }),
      });

      expect(
        reducers(
          initialState,
          vlanActions.configureDHCPStart({ item: { id: 0 } })
        )
      ).toEqual(
        factory.vlanState({
          statuses: factory.vlanStatuses({
            0: factory.vlanStatus({ configuringDHCP: true }),
          }),
        })
      );
    });

    it("reduces configureDHCPSuccess", () => {
      const initialState = factory.vlanState({
        statuses: factory.vlanStatuses({
          0: factory.vlanStatus({ configuringDHCP: true }),
        }),
      });

      expect(
        reducers(
          initialState,
          vlanActions.configureDHCPSuccess({
            item: { id: 0 },
          })
        )
      ).toEqual(
        factory.vlanState({
          statuses: factory.vlanStatuses({
            0: factory.vlanStatus({ configuringDHCP: false }),
          }),
        })
      );
    });

    it("reduces configureDHCPError", () => {
      const initialState = factory.vlanState({
        statuses: factory.vlanStatuses({
          0: factory.vlanStatus({ configuringDHCP: true }),
        }),
      });

      expect(
        reducers(
          initialState,
          vlanActions.configureDHCPError({
            error: true,
            item: { id: 0 },
            payload: "You broke it",
          })
        )
      ).toEqual(
        factory.vlanState({
          errors: "You broke it",
          eventErrors: [
            factory.vlanEventError({
              error: "You broke it",
              event: "configureDHCP",
              id: 0,
            }),
          ],
          statuses: factory.vlanStatuses({
            0: factory.vlanStatus({ configuringDHCP: false }),
          }),
        })
      );
    });
  });

  describe("subnet/createNotify", () => {
    it("updates VLAN subnet_ids when a subnet is created", () => {
      const vlan1 = factory.vlan({ id: 1, subnet_ids: [] });
      const vlan2 = factory.vlan({ id: 2, subnet_ids: [] });
      const initialState = factory.vlanState({
        items: [vlan1, vlan2],
      });
      const subnet = factory.subnet({ id: 3, vlan: 1 });
      const expectedVlans = [{ ...vlan1, subnet_ids: [subnet.id] }, vlan2];

      expect(
        reducers(initialState, subnetActions.createNotify(subnet))
      ).toEqual(
        factory.vlanState({
          items: expectedVlans,
        })
      );
    });
  });
});
