import { http, HttpResponse } from "msw";

import { fabricV3 } from "../factories/fabric";
import { BASE_URL } from "../utils";

import type { ListFabricsError, ListFabricsResponse } from "@/app/apiclient";

const mockFabrics: ListFabricsResponse = {
  items: fabricV3.buildList(5),
  total: 5,
};

const mockListFabricsError: ListFabricsError = {
  message: "Internal server error",
  code: 500,
  kind: "Error",
};

const fabricsResolvers = {
  listFabrics: {
    resolved: false,
    handler: (data: ListFabricsResponse = mockFabrics) =>
      http.get(`${BASE_URL}MAAS/a/v3/fabrics`, () => {
        fabricsResolvers.listFabrics.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListFabricsError = mockListFabricsError) =>
      http.get(`${BASE_URL}MAAS/a/v3/fabrics`, () => {
        fabricsResolvers.listFabrics.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
};

export { fabricsResolvers, mockFabrics };
