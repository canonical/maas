import { Factory } from "fishery";

import type {
  ImageResponse,
  ImageStatisticResponse,
  ImageStatusResponse,
  UiSourceAvailableImageResponse,
} from "@/app/apiclient";
import { timestamp } from "@/testing/factories/general";

export const imageFactory = Factory.define<ImageResponse>(({ sequence }) => ({
  id: sequence,
  os: "ubuntu",
  release: "noble",
  title: "24.04 LTS",
  architecture: "amd64",
  boot_source_id: 1,
}));

export const imageStatisticsFactory = Factory.define<ImageStatisticResponse>(
  ({ sequence }) => ({
    id: sequence,
    last_updated: timestamp("Tue, 08 Jun. 2021 02:12:47"),
    last_deployed: timestamp("Tue, 08 Jun. 2021 02:12:47"),
    size: "650.4 MB",
    node_count: 0,
    deploy_to_memory: true,
  })
);

export const imageStatusFactory = Factory.define<ImageStatusResponse>(
  ({ sequence }) => ({
    id: sequence,
    status: "Ready",
    update_status: "No updates available",
    sync_percentage: 0,
    selected: true,
  })
);

export const availableImageFactory =
  Factory.define<UiSourceAvailableImageResponse>(() => ({
    os: "ubuntu",
    release: "noble",
    title: "24.04 LTS",
    architecture: "amd64",
    source_id: 1,
    source_url: "maas.io",
  }));
