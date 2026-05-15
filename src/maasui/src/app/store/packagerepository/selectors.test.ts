import packagerepository from "./selectors";

import * as factory from "@/testing/factories";

describe("packagerepository selectors", () => {
  it("can get repository items", () => {
    const items = [factory.packageRepository(), factory.packageRepository()];
    const state = factory.rootState({
      packagerepository: factory.packageRepositoryState({
        items,
      }),
    });
    expect(packagerepository.all(state)).toEqual(items);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      packagerepository: factory.packageRepositoryState({
        loading: true,
      }),
    });
    expect(packagerepository.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      packagerepository: factory.packageRepositoryState({
        loaded: true,
      }),
    });
    expect(packagerepository.loaded(state)).toEqual(true);
  });

  it("can get the saving state", () => {
    const state = factory.rootState({
      packagerepository: factory.packageRepositoryState({
        saving: true,
      }),
    });
    expect(packagerepository.saving(state)).toEqual(true);
  });

  it("can get the saved state", () => {
    const state = factory.rootState({
      packagerepository: factory.packageRepositoryState({
        saved: true,
      }),
    });
    expect(packagerepository.saved(state)).toEqual(true);
  });

  it("can get packagerepository errors", () => {
    const state = factory.rootState({
      packagerepository: factory.packageRepositoryState({
        errors: { name: "Name already exists" },
      }),
    });
    expect(packagerepository.errors(state)).toStrictEqual({
      name: "Name already exists",
    });
  });

  it("can get the count", () => {
    const state = factory.rootState({
      packagerepository: factory.packageRepositoryState({
        loading: true,
        items: [factory.packageRepository(), factory.packageRepository()],
      }),
    });
    expect(packagerepository.count(state)).toEqual(2);
  });

  it("can get a repository by id", () => {
    const items = [
      factory.packageRepository({ id: 101 }),
      factory.packageRepository({ id: 123 }),
    ];
    const state = factory.rootState({
      packagerepository: factory.packageRepositoryState({
        loading: true,
        items,
      }),
    });
    expect(packagerepository.getById(state, 101)).toStrictEqual(items[0]);
  });

  it("can search items", () => {
    const items = [
      factory.packageRepository({ name: "main_archive" }),
      factory.packageRepository({ url: "www.main.com" }),
      factory.packageRepository(),
    ];
    const state = factory.rootState({
      packagerepository: factory.packageRepositoryState({
        items,
      }),
    });
    expect(packagerepository.search(state, "main")).toEqual([
      items[0],
      items[1],
    ]);
  });

  it("can search by display name", () => {
    const items = [
      factory.packageRepository({ name: "main_archive", default: true }),
      factory.packageRepository({ url: "www.main.com" }),
      factory.packageRepository(),
    ];
    const state = factory.rootState({
      packagerepository: factory.packageRepositoryState({
        items,
      }),
    });
    expect(packagerepository.search(state, "Ubuntu")).toEqual([items[0]]);
  });

  it("can get the main archive", () => {
    const [mainArchive, otherArchive] = [
      factory.packageRepository({ name: "main_archive", default: true }),
      factory.packageRepository({ name: "other_archive", default: true }),
    ];
    const state = factory.rootState({
      packagerepository: factory.packageRepositoryState({
        items: [mainArchive, otherArchive],
      }),
    });
    expect(packagerepository.mainArchive(state)).toEqual(mainArchive);
  });

  it("can get the ports archive", () => {
    const [portsArchive, otherArchive] = [
      factory.packageRepository({ name: "ports_archive", default: true }),
      factory.packageRepository({ name: "other_archive", default: true }),
    ];
    const state = factory.rootState({
      packagerepository: factory.packageRepositoryState({
        items: [portsArchive, otherArchive],
      }),
    });
    expect(packagerepository.portsArchive(state)).toEqual(portsArchive);
  });
});
