import { createSlice } from "@reduxjs/toolkit";
import type { PayloadAction } from "@reduxjs/toolkit";

import type { Config, ConfigState, ConfigValues } from "./types";

import { genericInitialState } from "@/app/store/utils/slice";

const statusSlice = createSlice({
  name: "config",
  initialState: genericInitialState as ConfigState,
  reducers: {
    fetch: {
      prepare: () => ({
        meta: {
          model: "config",
          method: "list",
        },
        payload: null,
      }),
      reducer: () => {},
    },
    fetchStart: (state: ConfigState) => {
      state.loading = true;
    },
    fetchError: (
      state: ConfigState,
      action: PayloadAction<ConfigState["errors"]>
    ) => {
      state.errors = action.payload;
      state.loading = false;
    },
    fetchSuccess: (
      state: ConfigState,
      action: PayloadAction<Config<ConfigValues>[]>
    ) => {
      state.loading = false;
      state.loaded = true;
      state.items = action.payload;
    },
    update: {
      prepare: <V extends ConfigValues>(
        values: Record<string, Config<V>["value"]>
      ) => {
        const params = {
          items: values,
        };
        return {
          meta: {
            model: "config",
            method: "bulk_update",
          },
          payload: {
            params,
          },
        };
      },
      reducer: () => {},
    },
    updateStart: (state: ConfigState) => {
      state.saved = false;
      state.saving = true;
    },
    updateError: (
      state: ConfigState,
      action: PayloadAction<ConfigState["errors"]>
    ) => {
      state.errors = action.payload;
      state.saving = false;
    },
    updateSuccess: (state: ConfigState) => {
      state.errors = null;
      state.saved = true;
      state.saving = false;
    },
    updateNotify: (
      state: ConfigState,
      action: PayloadAction<Config<ConfigValues>>
    ) => {
      state.items = state.items.map((item) =>
        item.name === action.payload?.name ? action.payload : item
      );
    },
    cleanup: (state: ConfigState) => {
      state.errors = null;
      state.saved = false;
      state.saving = false;
    },
  },
});

export const { actions } = statusSlice;

export default statusSlice.reducer;
