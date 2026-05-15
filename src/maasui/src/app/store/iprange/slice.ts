import { createSlice } from "@reduxjs/toolkit";

import { IPRangeMeta } from "./types";
import type {
  CreateParams,
  IPRangeState,
  UpdateParams,
  IPRange,
} from "./types";

import {
  generateCommonReducers,
  generateGetReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

const ipRangeSlice = createSlice({
  name: IPRangeMeta.MODEL,
  initialState: genericInitialState as IPRangeState,
  reducers: {
    ...generateCommonReducers<
      IPRangeState,
      IPRangeMeta.PK,
      CreateParams,
      UpdateParams
    >({
      modelName: IPRangeMeta.MODEL,
      primaryKey: IPRangeMeta.PK,
    }),
    ...generateGetReducers<IPRangeState, IPRange, IPRangeMeta.PK>({
      modelName: IPRangeMeta.MODEL,
      primaryKey: IPRangeMeta.PK,
    }),
  },
});

export const { actions } = ipRangeSlice;

export default ipRangeSlice.reducer;
