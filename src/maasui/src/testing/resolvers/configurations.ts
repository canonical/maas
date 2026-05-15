import { http, HttpResponse } from "msw";

import { BASE_URL } from "../utils";

import type {
  SetConfigurationError,
  SetConfigurationsError,
  GetConfigurationError,
  GetConfigurationResponse,
  GetConfigurationsError,
  GetConfigurationsResponse,
} from "@/app/apiclient";
import { config as configFactory } from "@/testing/factories";

const mockConfigurations: GetConfigurationsResponse = {
  items: [configFactory()],
};

const mockGetConfigurationsError: GetConfigurationsError = {
  message: "Internal server error",
  code: 500,
  kind: "Error",
};

const mockGetConfigurationError: GetConfigurationError = {
  message: "Configuration not found",
  code: 404,
  kind: "Error",
};

const mockSetConfigurationError: SetConfigurationError = {
  message: "Unprocessable entity",
  code: 422,
  kind: "Error",
};

const configurationsResolvers = {
  listConfigurations: {
    resolved: false,
    handler: (data: GetConfigurationsResponse = mockConfigurations) =>
      http.get(`${BASE_URL}MAAS/a/v3/configurations`, () => {
        configurationsResolvers.listConfigurations.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: GetConfigurationsError = mockGetConfigurationsError) =>
      http.get(`${BASE_URL}MAAS/a/v3/configurations`, () => {
        configurationsResolvers.listConfigurations.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  getConfiguration: {
    resolved: false,
    handler: (data: GetConfigurationResponse = mockConfigurations.items[0]) =>
      http.get(`${BASE_URL}MAAS/a/v3/configurations/:id`, () => {
        configurationsResolvers.getConfiguration.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: GetConfigurationError = mockGetConfigurationError) =>
      http.get(`${BASE_URL}MAAS/a/v3/configurations/:id`, () => {
        configurationsResolvers.getConfiguration.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  setConfiguration: {
    resolved: false,
    handler: () =>
      http.put(`${BASE_URL}MAAS/a/v3/configurations/:id`, () => {
        configurationsResolvers.setConfiguration.resolved = true;
        return HttpResponse.json(configFactory());
      }),
    error: (error: SetConfigurationError = mockSetConfigurationError) =>
      http.put(`${BASE_URL}MAAS/a/v3/configurations/:id`, () => {
        configurationsResolvers.setConfiguration.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  setBulkConfigurations: {
    resolved: false,
    handler: () =>
      http.put(`${BASE_URL}MAAS/a/v3/configurations`, () => {
        configurationsResolvers.setBulkConfigurations.resolved = true;
        // The success response on this endpoint is empty, according to the open API spec
        return HttpResponse.json({}, { status: 200 });
      }),
    error: (error: SetConfigurationsError = mockSetConfigurationError) =>
      http.put(`${BASE_URL}MAAS/a/v3/configurations`, () => {
        configurationsResolvers.setBulkConfigurations.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
};

export { configurationsResolvers, mockConfigurations };
