import { http, HttpResponse } from "msw";

import type { SyncBootsourceBootsourceselectionError } from "@/app/apiclient";
import { BASE_URL } from "@/testing/utils";

const mockSyncError: SyncBootsourceBootsourceselectionError = {
  message: "Conflict",
  code: 409,
  kind: "Error",
};

const imageSyncResolvers = {
  startSynchronization: {
    resolved: false,
    handler: () =>
      http.post(
        `${BASE_URL}MAAS/a/v3/boot_sources/:boot_source_id/selections/:id\\:sync`,
        () => {
          imageSyncResolvers.startSynchronization.resolved = true;
          return HttpResponse.json({}, { status: 202 });
        }
      ),
    error: (error: SyncBootsourceBootsourceselectionError = mockSyncError) =>
      http.post(
        `${BASE_URL}MAAS/a/v3/boot_sources/:boot_source_id/selections/:id\\:sync`,
        () => {
          imageSyncResolvers.startSynchronization.resolved = true;
          return HttpResponse.json(error, { status: error.code });
        }
      ),
  },
  stopSynchronization: {
    resolved: false,
    handler: () =>
      http.post(
        `${BASE_URL}MAAS/a/v3/boot_sources/:boot_source_id/selections/:id\\:stop_sync`,
        () => {
          imageSyncResolvers.stopSynchronization.resolved = true;
          return HttpResponse.json({}, { status: 200 });
        }
      ),
    error: (error: SyncBootsourceBootsourceselectionError = mockSyncError) =>
      http.post(
        `${BASE_URL}MAAS/a/v3/boot_sources/:boot_source_id/selections/:id\\:stop_sync`,
        () => {
          imageSyncResolvers.stopSynchronization.resolved = true;
          return HttpResponse.json(error, { status: error.code });
        }
      ),
  },
};

export { imageSyncResolvers };
