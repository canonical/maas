import { http, HttpResponse } from "msw";

import { packageRepository as packageRepositoryFactory } from "../factories";
import { BASE_URL } from "../utils";

import type {
  CreatePackageRepositoryError,
  DeletePackageRepositoryError,
  GetPackageRepositoryError,
  GetPackageRepositoryResponse,
  ListPackageRepositoriesError,
  ListPackageRepositoriesResponse,
  UpdatePackageRepositoryError,
} from "@/app/apiclient";

const mockPackageRepositories: ListPackageRepositoriesResponse = {
  items: [
    packageRepositoryFactory({ id: 1 }),
    packageRepositoryFactory({ id: 2 }),
    packageRepositoryFactory({ id: 3 }),
  ],
  total: 3,
};

const mockPackageRepositoriesError: ListPackageRepositoriesError = {
  code: 500,
  message: "Internal Server Error",
  kind: "Error", // This will always be 'Error' for every error response
};

const mockGetPackageRepoError: GetPackageRepositoryError = {
  code: 404,
  message: "Repository not found",
  kind: "Error",
};

const mockCreatePackageRepoError: CreatePackageRepositoryError = {
  code: 409,
  message: "Conflicting resource",
  kind: "Error",
};

const mockUpdatePackageRepoError: UpdatePackageRepositoryError = {
  code: 422,
  message: "Unprocessable entity",
  kind: "Error",
};

const mockDeletePackageRepoError: DeletePackageRepositoryError = {
  code: 404,
  message: "Repository not found",
  kind: "Error",
};

const packageRepositoriesResolvers = {
  listPackageRepositories: {
    resolved: false,
    handler: (
      data: ListPackageRepositoriesResponse = mockPackageRepositories
    ) =>
      http.get(`${BASE_URL}MAAS/a/v3/package_repositories`, () => {
        packageRepositoriesResolvers.listPackageRepositories.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (
      error: ListPackageRepositoriesError = mockPackageRepositoriesError
    ) =>
      http.get(`${BASE_URL}MAAS/a/v3/package_repositories`, () => {
        packageRepositoriesResolvers.listPackageRepositories.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  getPackageRepository: {
    resolved: false,
    handler: (data?: GetPackageRepositoryResponse) =>
      http.get(
        `${BASE_URL}MAAS/a/v3/package_repositories/:id`,
        ({ params }) => {
          if (data) {
            packageRepositoriesResolvers.getPackageRepository.resolved = true;
            return HttpResponse.json(data);
          } else {
            const id = Number(params.id);
            if (!id) return HttpResponse.error();

            const packageRepository = mockPackageRepositories.items.find(
              (packageRepository) => packageRepository.id === id
            );
            packageRepositoriesResolvers.getPackageRepository.resolved = true;
            return packageRepository
              ? HttpResponse.json(packageRepository)
              : HttpResponse.error();
          }
        }
      ),
    error: (error: GetPackageRepositoryError = mockGetPackageRepoError) =>
      http.get(`${BASE_URL}MAAS/a/v3/package_repositories/:id`, () => {
        packageRepositoriesResolvers.getPackageRepository.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  createPackageRepository: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/package_repositories`, () => {
        packageRepositoriesResolvers.createPackageRepository.resolved = true;
        return HttpResponse.json({ id: 1 });
      }),
    error: (error: CreatePackageRepositoryError = mockCreatePackageRepoError) =>
      http.post(`${BASE_URL}MAAS/a/v3/package_repositories`, () => {
        packageRepositoriesResolvers.createPackageRepository.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  updatePackageRepository: {
    resolved: false,
    handler: () =>
      http.put(`${BASE_URL}MAAS/a/v3/package_repositories/:id`, () => {
        packageRepositoriesResolvers.updatePackageRepository.resolved = true;
        return HttpResponse.json({ id: 1 });
      }),
    error: (error: UpdatePackageRepositoryError = mockUpdatePackageRepoError) =>
      http.put(`${BASE_URL}MAAS/a/v3/package_repositories/:id`, () => {
        packageRepositoriesResolvers.updatePackageRepository.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  deletePackageRepository: {
    resolved: false,
    handler: () =>
      http.delete(`${BASE_URL}MAAS/a/v3/package_repositories/:id`, () => {
        packageRepositoriesResolvers.deletePackageRepository.resolved = true;
        return HttpResponse.json({}, { status: 204 });
      }),
    error: (error: DeletePackageRepositoryError = mockDeletePackageRepoError) =>
      http.delete(`${BASE_URL}MAAS/a/v3/package_repositories/:id`, () => {
        packageRepositoriesResolvers.deletePackageRepository.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
};

export { packageRepositoriesResolvers, mockPackageRepositories };
