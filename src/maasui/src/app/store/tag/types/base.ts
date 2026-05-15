import type { APIError } from "@/app/base/types";
import type { TimestampedModel } from "@/app/store/types/model";
import type { GenericState } from "@/app/store/types/state";

export type Tag = TimestampedModel & {
  comment: string;
  controller_count: number;
  definition: string;
  device_count: number;
  kernel_opts: string | null;
  machine_count: number;
  name: string;
};

export type TagStateList = {
  items: Tag[] | null;
  errors: APIError;
  loaded: boolean;
  loading: boolean;
};

export type TagStateLists = Record<string, TagStateList>;

export type TagState = GenericState<Tag, APIError> & {
  lists: TagStateLists;
};
