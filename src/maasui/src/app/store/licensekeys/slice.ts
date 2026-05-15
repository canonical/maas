import type { PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import { LicenseKeysMeta } from "./types";
import type {
  CreateParams,
  LicenseKeys,
  LicenseKeysState,
  UpdateParams,
} from "./types";

import {
  generateCommonReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

const licenseKeysSlice = createSlice({
  name: LicenseKeysMeta.MODEL,
  initialState: genericInitialState as LicenseKeysState,
  reducers: {
    ...generateCommonReducers<
      LicenseKeysState,
      LicenseKeysMeta.PK,
      CreateParams,
      UpdateParams
    >({
      modelName: LicenseKeysMeta.MODEL,
      primaryKey: LicenseKeysMeta.PK,
    }),
    create: {
      prepare: (params: CreateParams) => ({
        payload: params,
      }),
      reducer: () => {},
    },
    delete: {
      prepare: (params: LicenseKeys) => ({
        payload: params,
      }),
      reducer: () => {},
    },
    dismissStart: (state: LicenseKeysState) => {
      state.saved = false;
      state.saving = true;
    },
    dismissError: (
      state: LicenseKeysState,
      action: PayloadAction<LicenseKeysState["errors"]>
    ) => {
      state.errors = action.payload;
      state.saving = false;
    },
    deleteSuccess: (state: LicenseKeysState, action) => {
      state.errors = null;
      state.saved = true;
      state.saving = false;
      const deleteIndex = state.items.findIndex(
        (item: LicenseKeys) =>
          item.osystem === action.payload.osystem &&
          item.distro_series === action.payload.distro_series
      );
      state.items.splice(deleteIndex, 1);
    },
    fetch: {
      prepare: () => ({
        payload: null,
      }),
      reducer: () => {},
    },
    update: {
      prepare: (params: UpdateParams) => ({
        payload: params,
      }),
      reducer: () => {},
    },
    updateSuccess: (state: LicenseKeysState, action) => {
      state.errors = null;
      state.saved = true;
      state.saving = false;
      const updateIndex = state.items.findIndex(
        (item: LicenseKeys) =>
          item.osystem === action.payload.osystem &&
          item.distro_series === action.payload.distro_series
      );
      state.items[updateIndex] = action.payload;
    },
  },
});

export const { actions } = licenseKeysSlice;

export default licenseKeysSlice.reducer;
