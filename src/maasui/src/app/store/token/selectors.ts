import { TokenMeta } from "@/app/store/token/types";
import type { Token, TokenState } from "@/app/store/token/types";
import { generateBaseSelectors } from "@/app/store/utils";

const selectors = generateBaseSelectors<TokenState, Token, TokenMeta.PK>(
  TokenMeta.MODEL,
  TokenMeta.PK
);

export default selectors;
