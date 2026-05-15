import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

describe("packagerepository reducer", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual(
      factory.packageRepositoryState()
    );
  });

  it("reduces fetchStart", () => {
    expect(
      reducers(
        factory.packageRepositoryState({ loading: false }),
        actions.fetchStart()
      )
    ).toEqual(
      factory.packageRepositoryState({
        loading: true,
      })
    );
  });

  it("reduces fetchSuccess", () => {
    const items = [factory.packageRepository(), factory.packageRepository()];
    expect(
      reducers(
        factory.packageRepositoryState({
          items: [],
          loaded: false,
          loading: true,
        }),
        actions.fetchSuccess(items)
      )
    ).toEqual(
      factory.packageRepositoryState({
        items,
        loaded: true,
        loading: false,
      })
    );
  });

  it("reduces createStart", () => {
    expect(
      reducers(
        factory.packageRepositoryState({
          saved: true,
          saving: false,
        }),
        actions.createStart()
      )
    ).toEqual(
      factory.packageRepositoryState({
        saved: false,
        saving: true,
      })
    );
  });

  it("reduces createSuccess", () => {
    expect(
      reducers(
        factory.packageRepositoryState({
          errors: { name: "Name already exists" },
          saved: false,
          saving: true,
        }),
        actions.createSuccess()
      )
    ).toEqual(
      factory.packageRepositoryState({
        errors: null,
        saved: true,
        saving: false,
      })
    );
  });

  it("reduces createError", () => {
    expect(
      reducers(
        factory.packageRepositoryState({
          errors: null,
          saving: true,
        }),
        actions.createError("Could not create repository")
      )
    ).toEqual(
      factory.packageRepositoryState({
        errors: "Could not create repository",
        saving: false,
      })
    );
  });

  it("reduces createNotify", () => {
    const items = [factory.packageRepository(), factory.packageRepository()];
    expect(
      reducers(
        factory.packageRepositoryState({
          items: [items[0]],
        }),
        actions.createNotify(items[1])
      )
    ).toEqual(
      factory.packageRepositoryState({
        items,
      })
    );
  });

  it("reduces updateStart", () => {
    expect(
      reducers(
        factory.packageRepositoryState({
          saved: true,
          saving: false,
        }),
        actions.updateStart()
      )
    ).toEqual(
      factory.packageRepositoryState({
        saved: false,
        saving: true,
      })
    );
  });

  it("reduces updateSuccess", () => {
    expect(
      reducers(
        factory.packageRepositoryState({
          errors: { name: "Name already exists" },
          saved: false,
          saving: true,
        }),
        actions.updateSuccess()
      )
    ).toEqual(
      factory.packageRepositoryState({
        errors: null,
        saved: true,
        saving: false,
      })
    );
  });

  it("reduces updateError", () => {
    expect(
      reducers(
        factory.packageRepositoryState({
          errors: null,
          saving: true,
        }),
        actions.updateError("Could not update repository")
      )
    ).toEqual(
      factory.packageRepositoryState({
        errors: "Could not update repository",
        saving: false,
      })
    );
  });

  it("reduces updateNotify", () => {
    const items = [factory.packageRepository(), factory.packageRepository()];
    const updated = { ...items[1], name: "newName" };
    expect(
      reducers(
        factory.packageRepositoryState({
          items,
        }),
        actions.updateNotify(updated)
      )
    ).toEqual(
      factory.packageRepositoryState({
        items: [items[0], updated],
      })
    );
  });

  it("reduces deleteStart", () => {
    expect(
      reducers(
        factory.packageRepositoryState({
          saved: true,
          saving: false,
        }),
        actions.deleteStart()
      )
    ).toEqual(
      factory.packageRepositoryState({
        saved: false,
        saving: true,
      })
    );
  });

  it("reduces deleteSuccess", () => {
    expect(
      reducers(
        factory.packageRepositoryState({
          errors: { name: "Name already exists" },
          saved: false,
          saving: true,
        }),
        actions.deleteSuccess()
      )
    ).toEqual(
      factory.packageRepositoryState({
        errors: null,
        saved: true,
        saving: false,
      })
    );
  });

  it("reduces deleteError", () => {
    expect(
      reducers(
        factory.packageRepositoryState({
          errors: null,
          saving: true,
        }),
        actions.deleteError("Could not delete repository")
      )
    ).toEqual(
      factory.packageRepositoryState({
        errors: "Could not delete repository",
        saving: false,
      })
    );
  });

  it("reduces deleteNotify", () => {
    const items = [factory.packageRepository(), factory.packageRepository()];
    expect(
      reducers(
        factory.packageRepositoryState({
          items,
          loaded: false,
          loading: false,
          saved: false,
          saving: false,
        }),
        actions.deleteNotify(items[1].id)
      )
    ).toEqual(
      factory.packageRepositoryState({
        items: [items[0]],
      })
    );
  });
});
