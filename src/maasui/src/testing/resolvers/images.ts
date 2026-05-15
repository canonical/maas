import { http, HttpResponse } from "msw";

import type {
  BulkCreateSelectionsError,
  GetAllAvailableImagesError,
  ImageListResponse,
  ImageStatisticListResponse,
  ImageStatusListResponse,
  ListSelectionsError,
  ListSelectionStatisticError,
  ListSelectionStatusError,
  UiSourceAvailableImageListResponse,
} from "@/app/apiclient";
import {
  availableImageFactory,
  imageFactory,
  imageStatisticsFactory,
  imageStatusFactory,
} from "@/testing/factories/image";
import { BASE_URL } from "@/testing/utils";

const mockSelections: ImageListResponse = {
  items: [
    imageFactory.build({
      os: "ubuntu",
      release: "noble",
      title: "24.04 LTS",
    }),
    imageFactory.build({
      os: "ubuntu",
      release: "jammy",
      title: "22.04 LTS",
    }),
    imageFactory.build({
      os: "centos",
      release: "centos7",
      title: "7.0",
    }),
  ],
  total: 3,
};

const mockStatistics: ImageStatisticListResponse = {
  items: imageStatisticsFactory.buildList(3),
  total: 3,
};

const mockStatuses: ImageStatusListResponse = {
  items: imageStatusFactory.buildList(3),
  total: 3,
};

const mockAvailableSelections: UiSourceAvailableImageListResponse = {
  items: [
    availableImageFactory.build({
      os: "ubuntu",
      release: "noble",
      title: "24.04 LTS",
      architecture: "amd64",
    }),
    availableImageFactory.build({
      os: "ubuntu",
      release: "noble",
      title: "24.04 LTS",
      architecture: "arm64",
    }),
    availableImageFactory.build({
      os: "ubuntu",
      release: "jammy",
      title: "22.04 LTS",
      architecture: "amd64",
    }),
    availableImageFactory.build({
      os: "centos",
      release: "centos7",
      title: "7.0",
      architecture: "amd64",
    }),
  ],
};

const mockListImagesError: ListSelectionsError = {
  message: "Invalid",
  code: 422,
  kind: "Error",
};

const mockListImageStatisticsError: ListSelectionStatisticError = {
  message: "Not found",
  code: 404,
  kind: "Error",
};

const mockListImageStatusesError: ListSelectionStatusError = {
  message: "Not found",
  code: 404,
  kind: "Error",
};

const mockSaveSelectionsError: BulkCreateSelectionsError = {
  message: "Conflict",
  code: 409,
  kind: "Error",
};

const imageResolvers = {
  listSelections: {
    resolved: false,
    handler: (data: ImageListResponse = mockSelections) =>
      http.get(`${BASE_URL}MAAS/a/v3/selections`, () => {
        imageResolvers.listSelections.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListSelectionsError = mockListImagesError) =>
      http.get(`${BASE_URL}MAAS/a/v3/selections`, () => {
        imageResolvers.listSelections.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  listSelectionStatistics: {
    resolved: false,
    handler: (data: ImageStatisticListResponse = mockStatistics) =>
      http.get(`${BASE_URL}MAAS/a/v3/selections/statistics`, () => {
        imageResolvers.listSelectionStatistics.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (
      error: ListSelectionStatisticError = mockListImageStatisticsError
    ) =>
      http.get(`${BASE_URL}MAAS/a/v3/selections/statistics`, () => {
        imageResolvers.listSelectionStatistics.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  listSelectionStatuses: {
    resolved: false,
    handler: (data: ImageStatusListResponse = mockStatuses) =>
      http.get(`${BASE_URL}MAAS/a/v3/selections/statuses`, () => {
        imageResolvers.listSelectionStatuses.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListSelectionStatusError = mockListImageStatusesError) =>
      http.get(`${BASE_URL}MAAS/a/v3/selections/statuses`, () => {
        imageResolvers.listSelectionStatuses.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  listCustomImages: {
    resolved: false,
    handler: (data: ImageListResponse = { items: [], total: 0 }) =>
      http.get(`${BASE_URL}MAAS/a/v3/custom_images`, () => {
        imageResolvers.listCustomImages.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListSelectionsError = mockListImagesError) =>
      http.get(`${BASE_URL}MAAS/a/v3/custom_images`, () => {
        imageResolvers.listCustomImages.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  listCustomImageStatistics: {
    resolved: false,
    handler: (data: ImageStatisticListResponse = { items: [], total: 0 }) =>
      http.get(`${BASE_URL}MAAS/a/v3/custom_images/statistics`, () => {
        imageResolvers.listCustomImageStatistics.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (
      error: ListSelectionStatisticError = mockListImageStatisticsError
    ) =>
      http.get(`${BASE_URL}MAAS/a/v3/custom_images/statistics`, () => {
        imageResolvers.listCustomImageStatistics.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  listCustomImageStatuses: {
    resolved: false,
    handler: (data: ImageStatusListResponse = { items: [], total: 0 }) =>
      http.get(`${BASE_URL}MAAS/a/v3/custom_images/statuses`, () => {
        imageResolvers.listCustomImageStatuses.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListSelectionStatusError = mockListImageStatusesError) =>
      http.get(`${BASE_URL}MAAS/a/v3/custom_images/statuses`, () => {
        imageResolvers.listCustomImageStatuses.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  listAvailableSelections: {
    resolved: false,
    handler: (
      data: UiSourceAvailableImageListResponse = mockAvailableSelections
    ) =>
      http.get(`${BASE_URL}MAAS/a/v3/available_images`, () => {
        imageResolvers.listAvailableSelections.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: GetAllAvailableImagesError = mockListImagesError) =>
      http.get(`${BASE_URL}MAAS/a/v3/available_images`, () => {
        imageResolvers.listAvailableSelections.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  addSelections: {
    resolved: false,
    handler: (data: ImageListResponse = mockSelections) =>
      http.post(`${BASE_URL}MAAS/a/v3/selections`, () => {
        imageResolvers.addSelections.resolved = true;
        return HttpResponse.json(data, { status: 200 });
      }),
    error: (error: BulkCreateSelectionsError = mockSaveSelectionsError) =>
      http.post(`${BASE_URL}MAAS/a/v3/selections`, () => {
        imageResolvers.addSelections.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  deleteSelections: {
    resolved: false,
    handler: () =>
      http.delete(`${BASE_URL}MAAS/a/v3/selections`, () => {
        imageResolvers.deleteSelections.resolved = true;
        return HttpResponse.json({}, { status: 204 });
      }),
    error: (error: BulkCreateSelectionsError = mockSaveSelectionsError) =>
      http.delete(`${BASE_URL}MAAS/a/v3/selections`, () => {
        imageResolvers.deleteSelections.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  uploadCustomImage: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/custom_images`, () => {
        imageResolvers.uploadCustomImage.resolved = true;
        return HttpResponse.json({}, { status: 201 });
      }),
    error: (error: BulkCreateSelectionsError = mockSaveSelectionsError) =>
      http.post(`${BASE_URL}MAAS/a/v3/custom_images`, () => {
        imageResolvers.uploadCustomImage.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  deleteCustomImages: {
    resolved: false,
    handler: () =>
      http.delete(`${BASE_URL}MAAS/a/v3/custom_images`, () => {
        imageResolvers.deleteCustomImages.resolved = true;
        return HttpResponse.json({}, { status: 204 });
      }),
    error: (error: BulkCreateSelectionsError = mockSaveSelectionsError) =>
      http.delete(`${BASE_URL}MAAS/a/v3/custom_images`, () => {
        imageResolvers.deleteCustomImages.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
};

export {
  imageResolvers,
  mockSelections,
  mockStatistics,
  mockStatuses,
  mockAvailableSelections,
};
