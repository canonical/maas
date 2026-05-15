import { http, HttpResponse } from "msw";

import { switchFactory } from "../factories/switches";
import { BASE_URL } from "../utils";

import type {
  CreateSwitchError,
  DeleteSwitchError,
  GetSwitchError,
  ListSwitchesError,
  ListSwitchesResponse,
  UpdateSwitchError,
} from "@/app/apiclient";

const mockSwitches = { items: switchFactory.buildList(3), total: 3 };

const mockListSwitchesError: ListSwitchesError = {
  message: "Unauthorized",
  code: 401,
  kind: "Error",
};

const mockGetSwitchError: GetSwitchError = {
  message: "Not found",
  code: 404,
  kind: "Error",
};

const mockCreateSwitchError: CreateSwitchError = {
  message: "A switch with this MAC address already exists.",
  code: 409,
  kind: "Error",
};

const mockUpdateSwitchError: UpdateSwitchError = {
  message: "Internal server error",
  code: 500,
  kind: "Error",
};

const mockDeleteSwitchError: DeleteSwitchError = {
  message: "Not found",
  code: 404,
  kind: "Error",
};

const switchResolvers = {
  listSwitches: {
    resolved: false,
    handler: (data: ListSwitchesResponse = mockSwitches) =>
      http.get(`${BASE_URL}MAAS/a/v3/switches`, () => {
        switchResolvers.listSwitches.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListSwitchesError = mockListSwitchesError) =>
      http.get(`${BASE_URL}MAAS/a/v3/switches`, () => {
        switchResolvers.listSwitches.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  getSwitch: {
    resolved: false,
    handler: () =>
      http.get(`${BASE_URL}MAAS/a/v3/switches/:switch_id`, ({ params }) => {
        const id = Number(params.switch_id);
        if (!id) return HttpResponse.error();
        const sw = mockSwitches.items.find((s) => s.id === id);
        switchResolvers.getSwitch.resolved = true;
        return sw ? HttpResponse.json(sw) : HttpResponse.error();
      }),
    error: (error: GetSwitchError = mockGetSwitchError) =>
      http.get(`${BASE_URL}MAAS/a/v3/switches/:switch_id`, () => {
        switchResolvers.getSwitch.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  createSwitch: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/switches`, () => {
        switchResolvers.createSwitch.resolved = true;
        return HttpResponse.json({ id: 1 });
      }),
    error: (error: CreateSwitchError = mockCreateSwitchError) =>
      http.post(`${BASE_URL}MAAS/a/v3/switches`, () => {
        switchResolvers.createSwitch.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  updateSwitch: {
    resolved: false,
    handler: () =>
      http.patch(`${BASE_URL}MAAS/a/v3/switches/:switch_id`, () => {
        switchResolvers.updateSwitch.resolved = true;
        return HttpResponse.json({});
      }),
    error: (error: UpdateSwitchError = mockUpdateSwitchError) =>
      http.patch(`${BASE_URL}MAAS/a/v3/switches/:switch_id`, () => {
        switchResolvers.updateSwitch.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  deleteSwitch: {
    resolved: false,
    handler: () =>
      http.delete(`${BASE_URL}MAAS/a/v3/switches/:switch_id`, () => {
        switchResolvers.deleteSwitch.resolved = true;
        return HttpResponse.json({}, { status: 204 });
      }),
    error: (error: DeleteSwitchError = mockDeleteSwitchError) =>
      http.delete(`${BASE_URL}MAAS/a/v3/switches/:switch_id`, () => {
        switchResolvers.deleteSwitch.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
};

export { mockSwitches, switchResolvers };
