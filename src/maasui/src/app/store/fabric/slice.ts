import type { PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import { FabricMeta } from "./types";
import type { CreateParams, Fabric, FabricState, UpdateParams } from "./types";

import {
  generateCommonReducers,
  generateGetReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

const fabricSlice = createSlice({
  name: FabricMeta.MODEL,
  initialState: {
    ...genericInitialState,
    active: null,
  } as FabricState,
  reducers: {
    ...generateCommonReducers<
      FabricState,
      FabricMeta.PK,
      CreateParams,
      UpdateParams
    >({
      modelName: FabricMeta.MODEL,
      primaryKey: FabricMeta.PK,
    }),
    ...generateGetReducers<FabricState, Fabric, FabricMeta.PK>({
      modelName: FabricMeta.MODEL,
      primaryKey: FabricMeta.PK,
    }),
    setActive: {
      prepare: (id: Fabric[FabricMeta.PK] | null) => ({
        meta: {
          model: FabricMeta.MODEL,
          method: "set_active",
        },
        payload: {
          // Server unsets active item if primary key is not sent.
          params: id === null ? null : { [FabricMeta.PK]: id },
        },
      }),
      reducer: () => {},
    },
    setActiveError: (
      state: FabricState,
      action: PayloadAction<FabricState["errors"]>
    ) => {
      state.active = null;
      state.errors = action.payload;
    },
    setActiveSuccess: (
      state: FabricState,
      action: PayloadAction<Fabric | null>
    ) => {
      state.active = action.payload ? action.payload[FabricMeta.PK] : null;
    },
  },
});

export const { actions } = fabricSlice;

export default fabricSlice.reducer;
