import { define, extend } from "cooky-cutter";

import { model } from "./model";

import type { Token, TokenConsumer } from "@/app/store/token/types";
import type { Model } from "@/app/store/types/model";

export const tokenConsumer = define<TokenConsumer>({
  key: (i: number) => `consumer key ${i}`,
  name: (i: number) => `consumer name ${i}`,
});

export const token = extend<Model, Token>(model, {
  consumer: tokenConsumer,
  key: (i: number) => `token key ${i}`,
  secret: (i: number) => `secret key ${i}`,
});
