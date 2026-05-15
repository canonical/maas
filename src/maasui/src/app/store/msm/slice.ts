import type { PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import type { MsmState, MsmStatus } from "./types/base";

const initialState: MsmState = {
  status: null,
  errors: null,
  loading: false,
  loaded: false,
};

const msmSlice = createSlice({
  name: "msm",
  initialState,
  reducers: {
    fetch: {
      prepare: () => ({
        meta: {
          model: "msm",
          method: "status",
        },
        payload: null,
      }),
      reducer: () => {},
    },
    fetchSuccess(state, action: PayloadAction<MsmStatus>) {
      state.status = action.payload;
      state.loading = false;
      state.loaded = true;
      state.errors = null;
    },
    fetchError(state, action: PayloadAction<string>) {
      state.errors = action.payload;
      state.loading = false;
    },
  },
});

export const { actions: msmActions } = msmSlice;

export default msmSlice.reducer;
