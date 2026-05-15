import type { PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import { ScriptMeta } from "./types";
import type { Script, ScriptState } from "./types";

import {
  generateCommonReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

const scriptSlice = createSlice({
  name: ScriptMeta.MODEL,
  initialState: genericInitialState as ScriptState,
  reducers: {
    ...generateCommonReducers<ScriptState, ScriptMeta.PK, void, void>({
      modelName: ScriptMeta.MODEL,
      primaryKey: ScriptMeta.PK,
    }),
    get: {
      prepare: (
        id: Script[ScriptMeta.PK],
        fileId: string,
        revision?: number
      ) => ({
        meta: {
          model: ScriptMeta.MODEL,
          method: "get_script",
          fileContextKey: fileId,
          useFileContext: true,
        },
        payload: {
          params: {
            id,
            ...(revision ? { revision } : {}),
          },
        },
      }),
      reducer: () => {
        // no state changes needed
      },
    },
    getStart: (state: ScriptState, _action: PayloadAction<null>) => {
      state.loading = true;
    },
    getError: (
      state: ScriptState,
      action: PayloadAction<ScriptState["errors"]>
    ) => {
      state.errors = action.payload;
      state.loading = false;
    },
    getSuccess: (state: ScriptState) => {
      state.loading = false;
    },
    upload: {
      prepare: (
        type: Script["script_type"],
        contents: string,
        name?: Script["name"] | null
      ) => ({
        payload: {
          type,
          contents,
          name,
        },
      }),
      reducer: () => {
        // no state changes needed
      },
    },
    uploadError: (
      state: ScriptState,
      action: PayloadAction<ScriptState["errors"]>
    ) => {
      state.errors = action.payload;
      state.saving = false;
    },
    uploadStart: (state: ScriptState) => {
      state.saving = true;
    },
    uploadSuccess: (state: ScriptState) => {
      state.saved = true;
    },
  },
});

export const { actions } = scriptSlice;

export default scriptSlice.reducer;
