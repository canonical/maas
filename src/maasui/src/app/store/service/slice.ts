import { createSlice } from "@reduxjs/toolkit";

import type { ServiceState } from "./types";
import { ServiceMeta } from "./types";

import {
  generateCommonReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

const serviceSlice = createSlice({
  name: ServiceMeta.MODEL,
  initialState: genericInitialState as ServiceState,
  reducers: generateCommonReducers<ServiceState, ServiceMeta.PK, void, void>({
    modelName: ServiceMeta.MODEL,
    primaryKey: ServiceMeta.PK,
  }),
});

export const { actions } = serviceSlice;

export default serviceSlice.reducer;
