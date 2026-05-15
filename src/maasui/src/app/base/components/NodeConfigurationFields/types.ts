import type { Tag, TagMeta } from "@/app/store/tag/types";

export type NodeConfigurationValues = {
  description: string;
  tags: Tag[TagMeta.PK][];
  zone: string;
};
