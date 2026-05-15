import { http, HttpResponse } from "msw";

import { spaceV3 } from "../factories/space";
import { BASE_URL } from "../utils";

import type { ListSpacesError, ListSpacesResponse } from "@/app/apiclient";

const mockSpaces: ListSpacesResponse = {
  items: spaceV3.buildList(5),
  total: 5,
};

const mockListSpacesError: ListSpacesError = {
  message: "Internal server error",
  code: 500,
  kind: "Error",
};

const spacesResolvers = {
  listSpaces: {
    resolved: false,
    handler: (data: ListSpacesResponse = mockSpaces) =>
      http.get(`${BASE_URL}MAAS/a/v3/spaces`, () => {
        spacesResolvers.listSpaces.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListSpacesError = mockListSpacesError) =>
      http.get(`${BASE_URL}MAAS/a/v3/spaces`, () => {
        spacesResolvers.listSpaces.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
};

export { mockSpaces, spacesResolvers };
