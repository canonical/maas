import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

describe("domain reducer", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual({
      active: null,
      errors: null,
      items: [],
      loaded: false,
      loading: false,
      saved: false,
      saving: false,
    });
  });

  it("reduces fetch", () => {
    expect(reducers(undefined, actions.fetch())).toEqual(factory.domainState());
  });

  it("reduces fetchStart", () => {
    expect(reducers(undefined, actions.fetchStart())).toEqual(
      factory.domainState({
        loading: true,
      })
    );
  });

  it("reduces fetchSuccess", () => {
    const domains = [factory.domain()];
    const domainState = factory.domainState({
      items: [],
      loading: true,
    });
    expect(reducers(domainState, actions.fetchSuccess(domains))).toEqual(
      factory.domainState({
        loading: false,
        loaded: true,
        items: domains,
      })
    );
  });

  it("reduces fetchError", () => {
    const domainState = factory.domainState();

    expect(
      reducers(domainState, actions.fetchError("Could not fetch domains"))
    ).toEqual(
      factory.domainState({
        errors: "Could not fetch domains",
      })
    );
  });

  it("reduces createStart", () => {
    const domainState = factory.domainState({ saved: true });

    expect(reducers(domainState, actions.createStart())).toEqual(
      factory.domainState({
        saving: true,
      })
    );
  });

  it("reduces createError", () => {
    const domainState = factory.domainState();

    expect(
      reducers(
        domainState,
        actions.createError({ name: "Domain name already exists" })
      )
    ).toEqual(
      factory.domainState({
        errors: { name: "Domain name already exists" },
      })
    );
  });

  it("updates domains on createNotify", () => {
    const domains = [factory.domain({ id: 1 })];
    const newDomain = factory.domain({ id: 2 });
    const domainState = factory.domainState({
      items: domains,
    });

    expect(reducers(domainState, actions.createNotify(newDomain))).toEqual(
      factory.domainState({
        items: [...domains, newDomain],
      })
    );
  });

  it("reduces deleteStart", () => {
    const domains = [factory.domain({ id: 1 })];
    const domainState = factory.domainState({
      items: domains,
    });

    expect(reducers(domainState, actions.deleteStart())).toEqual(
      factory.domainState({
        items: domains,
        saving: true,
      })
    );
  });

  it("reduces deleteSuccess", () => {
    const domains = [factory.domain({ id: 1 })];
    const domainState = factory.domainState({
      items: domains,
      saving: true,
    });
    expect(reducers(domainState, actions.deleteSuccess())).toEqual(
      factory.domainState({
        items: domains,
        saved: true,
        saving: false,
      })
    );
  });

  it("reduces deleteError", () => {
    const domains = [factory.domain({ id: 1 })];
    const domainState = factory.domainState({
      items: domains,
    });
    expect(
      reducers(domainState, actions.deleteError("Domain cannot be deleted"))
    ).toEqual(
      factory.domainState({
        errors: "Domain cannot be deleted",
        items: domains,
      })
    );
  });

  it("reduces deleteNotify", () => {
    const domains = [factory.domain({ id: 1 }), factory.domain({ id: 2 })];
    const domainState = factory.domainState({
      items: domains,
    });

    expect(reducers(domainState, actions.deleteNotify(1))).toEqual(
      factory.domainState({
        items: [domains[1]],
      })
    );
  });

  it("reduces setDefaultStart", () => {
    const domainState = factory.domainState({
      saving: false,
    });

    expect(reducers(domainState, actions.setDefaultStart())).toEqual(
      factory.domainState({
        saving: true,
        saved: false,
      })
    );
  });

  it("reduces getStart", () => {
    const domainState = factory.domainState({ items: [], loading: false });

    expect(reducers(domainState, actions.getStart())).toEqual(
      factory.domainState({ loading: true })
    );
  });

  it("reduces getSuccess", () => {
    const newDomain = factory.domain();
    const domainState = factory.domainState({
      items: [],
      loading: true,
    });

    expect(reducers(domainState, actions.getSuccess(newDomain))).toEqual(
      factory.domainState({
        items: [newDomain],
        loading: false,
      })
    );
  });

  it("reduces getError", () => {
    const domainState = factory.domainState({ loading: true });

    expect(
      reducers(domainState, actions.getError("Could not get domain"))
    ).toEqual(
      factory.domainState({
        errors: "Could not get domain",
        loading: false,
      })
    );
  });

  it("reduces setDefaultError", () => {
    const domainState = factory.domainState({
      errors: null,
      saving: true,
    });

    expect(
      reducers(domainState, actions.setDefaultError("It didn't work"))
    ).toEqual(
      factory.domainState({
        errors: "It didn't work",
        saving: false,
      })
    );
  });

  it("reduces setDefaultSuccess", () => {
    const domain1 = factory.domain({ id: 1, is_default: true });
    const domain2 = factory.domain({ id: 2, is_default: false });
    const domainState = factory.domainState({
      items: [domain1, domain2],
      saving: true,
      saved: false,
    });

    expect(
      reducers(
        domainState,
        actions.setDefaultSuccess(factory.domain({ id: 2 }))
      )
    ).toEqual(
      factory.domainState({
        items: [
          { ...domain1, is_default: false },
          { ...domain2, is_default: true },
        ],
        saving: false,
        saved: true,
        errors: null,
      })
    );
  });

  it("reduces setActiveError", () => {
    const podState = factory.domainState({
      active: 1,
      errors: null,
    });

    expect(
      reducers(
        podState,
        actions.setActiveError("Domain with this id does not exist")
      )
    ).toEqual(
      factory.domainState({
        active: null,
        errors: "Domain with this id does not exist",
      })
    );
  });

  it("reduces setActiveSuccess", () => {
    const podState = factory.domainState({
      active: null,
    });

    expect(
      reducers(podState, actions.setActiveSuccess(factory.domain({ id: 101 })))
    ).toEqual(
      factory.domainState({
        active: 101,
      })
    );
  });
});
