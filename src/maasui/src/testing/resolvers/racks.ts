import { http, HttpResponse } from "msw";

import { rackFactory } from "../factories/racks";
import { BASE_URL } from "../utils";

import type {
  CreateRackError,
  DeleteRacksError,
  GenerateRackBootstrapTokenError,
  GetRackError,
  ListRacksError,
  ListRacksWithSummaryError,
  ListRacksWithSummaryResponse,
  UpdateRackError,
} from "@/app/apiclient";

const mockRacks = { items: rackFactory.buildList(15), total: 15 };

const mockListRacksError: ListRacksError = {
  message: "Unauthorized",
  code: 401,
  kind: "Error", // This will always be 'Error' for every error response
};

const mockGetRackError: GetRackError = {
  message: "Not found",
  code: 404,
  kind: "Error",
};

const mockCreateRackError: CreateRackError = {
  message: "A rack with this name already exists.",
  code: 409,
  kind: "Error",
};

const mockUpdateRackError: UpdateRackError = {
  message: "Internal server error",
  code: 500,
  kind: "Error",
};

const mockGenerateRackBootstrapTokenError: GenerateRackBootstrapTokenError = {
  message: "Bad request",
  code: 400,
  kind: "Error",
};

const rackResolvers = {
  listRacks: {
    resolved: false,
    handler: (data: ListRacksWithSummaryResponse = mockRacks) =>
      http.get(`${BASE_URL}MAAS/a/v3/racks_with_summary`, () => {
        rackResolvers.listRacks.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListRacksWithSummaryError = mockListRacksError) =>
      http.get(`${BASE_URL}MAAS/a/v3/racks_with_summary`, () => {
        rackResolvers.listRacks.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  getRack: {
    resolved: false,
    handler: () =>
      http.get(`${BASE_URL}MAAS/a/v3/racks/:id`, ({ params }) => {
        const id = Number(params.id);
        if (!id) return HttpResponse.error();

        const rack = mockRacks.items.find((rack) => rack.id === id);
        rackResolvers.getRack.resolved = true;
        return rack ? HttpResponse.json(rack) : HttpResponse.error();
      }),
    error: (error: GetRackError = mockGetRackError) =>
      http.get(`${BASE_URL}MAAS/a/v3/racks/:id`, () => {
        rackResolvers.getRack.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  createRack: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/racks`, () => {
        rackResolvers.createRack.resolved = true;
        return HttpResponse.json({ id: 1 });
      }),
    error: (error: CreateRackError = mockCreateRackError) =>
      http.post(`${BASE_URL}MAAS/a/v3/racks`, () => {
        rackResolvers.createRack.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  updateRack: {
    resolved: false,
    handler: () =>
      http.put(`${BASE_URL}MAAS/a/v3/racks/:id`, () => {
        rackResolvers.updateRack.resolved = true;
        return HttpResponse.json({});
      }),
    error: (error: UpdateRackError = mockUpdateRackError) =>
      http.put(`${BASE_URL}MAAS/a/v3/racks/:id`, () => {
        rackResolvers.updateRack.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  deleteRack: {
    resolved: false,
    handler: () =>
      http.delete(`${BASE_URL}MAAS/a/v3/racks/:id`, () => {
        rackResolvers.deleteRack.resolved = true;
        return HttpResponse.json({}, { status: 204 });
      }),
    error: (error: DeleteRacksError = mockGetRackError) =>
      http.delete(`${BASE_URL}MAAS/a/v3/racks/:id`, () => {
        rackResolvers.deleteRack.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  generateToken: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/racks/:id/tokens:generate`, () => {
        rackResolvers.generateToken.resolved = true;
        return HttpResponse.json({
          token: "generated-token",
          kind: "RackBootstrapToken",
        });
      }),
    error: (
      error: GenerateRackBootstrapTokenError = mockGenerateRackBootstrapTokenError
    ) =>
      http.post(`${BASE_URL}MAAS/a/v3/racks/:id/tokens:generate`, () => {
        rackResolvers.generateToken.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
};

export { mockRacks, rackResolvers };
