import { createSlice } from "@reduxjs/toolkit";

import { TokenMeta } from "./types";
import type { CreateParams, TokenState, UpdateParams } from "./types";

import {
  generateCommonReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

const tokenSlice = createSlice({
  name: TokenMeta.MODEL,
  initialState: genericInitialState as TokenState,
  reducers: generateCommonReducers<
    TokenState,
    TokenMeta.PK,
    CreateParams,
    UpdateParams
  >({
    modelName: TokenMeta.MODEL,
    primaryKey: TokenMeta.PK,
  }),
});

export const { actions } = tokenSlice;

export default tokenSlice.reducer;
