import { http, HttpResponse } from "msw";

import { resourcePool } from "../factories";
import { BASE_URL } from "../utils";

import type {
  CreateResourcePoolError,
  DeleteResourcePoolError,
  GetResourcePoolError,
  ListResourcePoolsError,
  ListResourcePoolsResponse,
  UpdateResourcePoolError,
} from "@/app/apiclient";

const mockPools: ListResourcePoolsResponse = {
  items: [
    resourcePool({
      name: "swimming",
      description: "place where you go to swim",
      machine_ready_count: 5,
      machine_total_count: 10,
      is_default: true,
      permissions: ["edit", "delete"],
    }),
    resourcePool({
      name: "gene",
      description: "a collection of genes",
      machine_ready_count: 1,
      machine_total_count: 2,
      is_default: false,
      permissions: [],
    }),
    resourcePool({
      name: "car",
      description: "a company car",
      machine_ready_count: 0,
      machine_total_count: 0,
      is_default: false,
      permissions: ["edit", "delete"],
    }),
  ],
  total: 3,
};

const mockListPoolsError: ListResourcePoolsError = {
  message: "Unauthorized",
  code: 401,
  kind: "Error", // This will always be 'Error' for every error response
};

const mockGetPoolError: GetResourcePoolError = {
  message: "Not found",
  code: 404,
  kind: "Error",
};

const mockCreatePoolError: CreateResourcePoolError = {
  message: "A pool with this name already exists.",
  code: 409,
  kind: "Error",
};

const mockUpdatePoolError: UpdateResourcePoolError = {
  message: "Internal server error",
  code: 500,
  kind: "Error",
};

const poolsResolvers = {
  listPools: {
    resolved: false,
    handler: (data: ListResourcePoolsResponse = mockPools) =>
      http.get(`${BASE_URL}MAAS/a/v3/resource_pools:statistics`, () => {
        poolsResolvers.listPools.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListResourcePoolsError = mockListPoolsError) =>
      http.get(`${BASE_URL}MAAS/a/v3/resource_pools:statistics`, () => {
        poolsResolvers.listPools.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  getPool: {
    resolved: false,
    handler: () =>
      http.get(`${BASE_URL}MAAS/a/v3/resource_pools/:id`, ({ params }) => {
        const id = Number(params.id);
        if (!id) return HttpResponse.error();

        const pool = mockPools.items.find((pool) => pool.id === id);
        poolsResolvers.getPool.resolved = true;
        return pool ? HttpResponse.json(pool) : HttpResponse.error();
      }),
    error: (error: GetResourcePoolError = mockGetPoolError) =>
      http.get(`${BASE_URL}MAAS/a/v3/users/:id`, () => {
        poolsResolvers.getPool.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  createPool: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/resource_pools`, () => {
        poolsResolvers.createPool.resolved = true;
        return HttpResponse.json({ id: 1 });
      }),
    error: (error: CreateResourcePoolError = mockCreatePoolError) =>
      http.post(`${BASE_URL}MAAS/a/v3/resource_pools`, () => {
        poolsResolvers.createPool.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  updatePool: {
    resolved: false,
    handler: () =>
      http.put(`${BASE_URL}MAAS/a/v3/resource_pools/:id`, () => {
        poolsResolvers.updatePool.resolved = true;
        return HttpResponse.json({});
      }),
    error: (error: UpdateResourcePoolError = mockUpdatePoolError) =>
      http.put(`${BASE_URL}MAAS/a/v3/resource_pools/:id`, () => {
        poolsResolvers.updatePool.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  deletePool: {
    resolved: false,
    handler: () =>
      http.delete(`${BASE_URL}MAAS/a/v3/resource_pools/:id`, () => {
        poolsResolvers.deletePool.resolved = true;
        return HttpResponse.json({}, { status: 204 });
      }),
    error: (error: DeleteResourcePoolError = mockGetPoolError) =>
      http.delete(`${BASE_URL}MAAS/a/v3/resource_pools/:id`, () => {
        poolsResolvers.deletePool.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
};

export { poolsResolvers, mockPools };
