import type {
  ImageResponse,
  ImageStatisticResponse,
  ImageStatusResponse,
} from "@/app/apiclient";

export type OptimisticStatuses = "OptimisticDownloading" | "OptimisticStopping";

export type OptimisticImageStatusResponse = Omit<
  ImageStatusResponse,
  "status" | "update_status"
> & {
  status: ImageStatusResponse["status"] | OptimisticStatuses;
  update_status: ImageStatusResponse["update_status"] | OptimisticStatuses;
};

export type Image = Omit<
  ImageResponse &
    Partial<ImageStatisticResponse> &
    Partial<OptimisticImageStatusResponse>,
  "id"
> & { id: string; isUpstream: boolean };

export enum BootResourceSourceType {
  MAAS_IO = "maas.io",
  CUSTOM = "custom",
}
