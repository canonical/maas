import type { PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import { SpaceMeta } from "./types";
import type { CreateParams, Space, SpaceState, UpdateParams } from "./types";

import {
  generateCommonReducers,
  generateGetReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

const spaceSlice = createSlice({
  name: SpaceMeta.MODEL,
  initialState: {
    ...genericInitialState,
    active: null,
  } as SpaceState,
  reducers: {
    ...generateCommonReducers<
      SpaceState,
      SpaceMeta.PK,
      CreateParams,
      UpdateParams
    >({
      modelName: SpaceMeta.MODEL,
      primaryKey: SpaceMeta.PK,
    }),
    ...generateGetReducers<SpaceState, Space, SpaceMeta.PK>({
      modelName: SpaceMeta.MODEL,
      primaryKey: SpaceMeta.PK,
    }),
    setActive: {
      prepare: (id: Space[SpaceMeta.PK] | null) => ({
        meta: {
          model: SpaceMeta.MODEL,
          method: "set_active",
        },
        payload: {
          // Server unsets active item if primary key is not sent.
          params: id === null ? null : { [SpaceMeta.PK]: id },
        },
      }),
      reducer: () => {},
    },
    setActiveError: (
      state: SpaceState,
      action: PayloadAction<SpaceState["errors"]>
    ) => {
      state.active = null;
      state.errors = action.payload;
    },
    setActiveSuccess: (
      state: SpaceState,
      action: PayloadAction<Space | null>
    ) => {
      state.active = action.payload ? action.payload[SpaceMeta.PK] : null;
    },
  },
});

export const { actions } = spaceSlice;

export default spaceSlice.reducer;
