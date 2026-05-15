import dhcpsnippet from "./selectors";

import * as factory from "@/testing/factories";

describe("dhcpsnippet selectors", () => {
  it("can get all items", () => {
    const items = [factory.dhcpSnippet(), factory.dhcpSnippet()];
    const state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        items,
      }),
    });
    expect(dhcpsnippet.all(state)).toEqual(items);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        loading: true,
      }),
    });
    expect(dhcpsnippet.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        loaded: true,
      }),
    });
    expect(dhcpsnippet.loaded(state)).toEqual(true);
  });

  it("can search items", () => {
    const items = [
      factory.dhcpSnippet({
        name: "class",
      }),
      factory.dhcpSnippet(),
      factory.dhcpSnippet({
        description: "boots class",
      }),
    ];
    const state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        items,
      }),
    });
    expect(dhcpsnippet.search(state, "class")).toEqual([items[0], items[2]]);
  });

  it("can get the count", () => {
    const state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        loading: true,
        items: [factory.dhcpSnippet(), factory.dhcpSnippet()],
      }),
    });
    expect(dhcpsnippet.count(state)).toEqual(2);
  });

  it("can get the saving state", () => {
    const state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        saving: true,
      }),
    });
    expect(dhcpsnippet.saving(state)).toEqual(true);
  });

  it("can get the saved state", () => {
    const state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        saved: true,
      }),
    });
    expect(dhcpsnippet.saved(state)).toEqual(true);
  });

  it("can get errors", () => {
    const state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        errors: { name: "Name not provided" },
      }),
    });
    expect(dhcpsnippet.errors(state)).toStrictEqual({
      name: "Name not provided",
    });
  });

  it("can get a dhcp snippet by id", () => {
    const items = [
      factory.dhcpSnippet({ id: 808 }),
      factory.dhcpSnippet({ id: 909 }),
    ];
    const state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        loading: true,
        items,
      }),
    });
    expect(dhcpsnippet.getById(state, 909)).toStrictEqual(items[1]);
  });

  it("can get dhcp snippets for a node", () => {
    const items = [
      factory.dhcpSnippet({ id: 707, node: "abc123" }),
      factory.dhcpSnippet({ id: 808 }),
      factory.dhcpSnippet({ id: 909, node: "abc123" }),
    ];
    const state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        items,
      }),
    });
    expect(dhcpsnippet.getByNode(state, "abc123")).toStrictEqual([
      items[0],
      items[2],
    ]);
  });

  it("can get dhcp snippets for subnets", () => {
    const items = [
      factory.dhcpSnippet({ id: 707, subnet: 1 }),
      factory.dhcpSnippet({ id: 808, subnet: 2 }),
      factory.dhcpSnippet({ id: 909, subnet: 3 }),
    ];
    const state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        items,
      }),
    });
    expect(dhcpsnippet.getBySubnets(state, [1, 3])).toStrictEqual([
      items[0],
      items[2],
    ]);
  });
});
