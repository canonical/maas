import {
  useCreatePackageRepository,
  useDeletePackageRepository,
  useGetPackageRepository,
  usePackageRepositories,
  useUpdatePackageRepository,
} from "./packageRepositories";

import {
  mockPackageRepositories,
  packageRepositoriesResolvers,
} from "@/testing/resolvers/packageRepositories";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  packageRepositoriesResolvers.listPackageRepositories.handler(),
  packageRepositoriesResolvers.getPackageRepository.handler(),
  packageRepositoriesResolvers.createPackageRepository.handler(),
  packageRepositoriesResolvers.updatePackageRepository.handler(),
  packageRepositoriesResolvers.deletePackageRepository.handler()
);

describe("usePackageRepositories", () => {
  it("should return a list of package repositories", async () => {
    const { result } = renderHookWithProviders(() => usePackageRepositories());

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.items).toEqual(mockPackageRepositories.items);
  });
});

describe("useGetPackageRepository", () => {
  it("should return a package repository", async () => {
    const { result } = renderHookWithProviders(() =>
      useGetPackageRepository({ path: { package_repository_id: 1 } })
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toMatchObject(mockPackageRepositories.items[0]);
  });

  it("should return an error if the pacakge repo does not exist", async () => {
    const { result } = renderHookWithProviders(() =>
      useGetPackageRepository({ path: { package_repository_id: 42069 } })
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});

describe("useCreatePackageRepository", () => {
  it("should create a package repository", async () => {
    const { result } = await renderHookWithProviders(() =>
      useCreatePackageRepository()
    );

    result.current.mutate({
      body: {
        name: "new repo",
        url: "https://fake.com",
        disable_sources: false,
      },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useUpdatePackageRepository", () => {
  it("should update a package repository", async () => {
    const { result } = renderHookWithProviders(() =>
      useUpdatePackageRepository()
    );

    result.current.mutate({
      path: {
        package_repository_id: 1,
      },
      body: {
        name: "new repo",
        url: "https://fake.com",
        disable_sources: false,
      },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useDeletePackageRepository", () => {
  it("should delete a package repository", async () => {
    const { result } = renderHookWithProviders(() =>
      useDeletePackageRepository()
    );

    result.current.mutate({
      path: {
        package_repository_id: 1,
      },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});
