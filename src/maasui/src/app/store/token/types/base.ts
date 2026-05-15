import type { APIError } from "@/app/base/types";
import type { Model } from "@/app/store/types/model";
import type { GenericState } from "@/app/store/types/state";

export type TokenConsumer = {
  key: string;
  name: string;
};

export type Token = Model & {
  consumer: TokenConsumer;
  key: string;
  secret: string;
};

export type TokenState = GenericState<Token, APIError>;
