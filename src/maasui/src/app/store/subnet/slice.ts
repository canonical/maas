import type { CaseReducer, PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import { SubnetMeta } from "./types";
import type {
  CreateParams,
  Subnet,
  SubnetScanResult,
  SubnetState,
  UpdateParams,
} from "./types";

import {
  generateCommonReducers,
  genericInitialState,
  generateStatusHandlers,
  updateErrors,
  generateGetReducers,
} from "@/app/store/utils/slice";
import type { GenericItemMeta } from "@/app/store/utils/slice";
import { isId } from "@/app/utils";

export const DEFAULT_STATUSES = {
  scanning: false,
};

const setErrors = (
  state: SubnetState,
  action: PayloadAction<SubnetState["errors"]> | null,
  event: string | null
): SubnetState =>
  updateErrors<SubnetState, SubnetMeta.PK>(state, action, event, SubnetMeta.PK);

const statusHandlers = generateStatusHandlers<
  SubnetState,
  Subnet,
  SubnetMeta.PK
>(
  SubnetMeta.PK,
  [
    {
      status: "scan",
      statusKey: "scanning",
    },
  ],
  setErrors
);

const subnetSlice = createSlice({
  name: SubnetMeta.MODEL,
  initialState: {
    ...genericInitialState,
    active: null,
    eventErrors: [],
    statuses: {},
  } as SubnetState,
  reducers: {
    ...generateCommonReducers<
      SubnetState,
      SubnetMeta.PK,
      CreateParams,
      UpdateParams
    >({
      modelName: SubnetMeta.MODEL,
      primaryKey: SubnetMeta.PK,
      setErrors,
    }),
    createNotify: (state: SubnetState, action: PayloadAction<Subnet>) => {
      // In the event that the server erroneously attempts to create an existing
      // subnet, due to a race condition etc., ensure we update instead of
      // creating duplicates.
      const existingIdx = state.items.findIndex(
        (draftItem) =>
          draftItem[SubnetMeta.PK] === action.payload[SubnetMeta.PK]
      );
      if (existingIdx !== -1) {
        state.items[existingIdx] = action.payload;
      } else {
        state.items.push(action.payload);
        state.statuses[action.payload[SubnetMeta.PK]] = DEFAULT_STATUSES;
      }
    },
    fetchSuccess: (state: SubnetState, action: PayloadAction<Subnet[]>) => {
      action.payload.forEach((newItem) => {
        // Add items that don't already exist in the store. Existing items
        // could be SubnetDetails so this would overwrite them with the base
        // type. Existing items will be kept up to date via the notify (sync)
        // messages.
        const existing = state.items.find(
          (draftItem) => draftItem[SubnetMeta.PK] === newItem[SubnetMeta.PK]
        );
        if (!existing) {
          state.items.push(newItem);
          state.statuses[newItem[SubnetMeta.PK]] = DEFAULT_STATUSES;
        }
      });
      state.loading = false;
      state.loaded = true;
    },
    ...generateGetReducers<SubnetState, Subnet, SubnetMeta.PK>({
      modelName: SubnetMeta.MODEL,
      primaryKey: SubnetMeta.PK,
      defaultStatuses: DEFAULT_STATUSES,
    }),
    scan: {
      prepare: (id: Subnet[SubnetMeta.PK]) => ({
        meta: {
          model: SubnetMeta.MODEL,
          method: "scan",
        },
        payload: {
          params: { [SubnetMeta.PK]: id },
        },
      }),
      reducer: () => {},
    },
    scanError: statusHandlers.scan.error as CaseReducer<
      SubnetState,
      PayloadAction<unknown>
    >,
    scanStart: statusHandlers.scan.start as CaseReducer<
      SubnetState,
      PayloadAction<unknown>
    >,
    scanSuccess: {
      prepare: ({ item, payload }) => ({
        meta: {
          item,
        },
        payload,
      }),
      reducer: (
        state: SubnetState,
        action: PayloadAction<SubnetScanResult, string, GenericItemMeta<Subnet>>
      ) => {
        const {
          meta,
          payload: { result, scan_started_on },
        } = action;
        const subnetId = meta.item?.[SubnetMeta.PK];
        if (isId(subnetId) && state.statuses[subnetId]) {
          state.statuses[subnetId].scanning = false;
        }
        // If websocket message was successful but nothing happened, set the
        // websocket result message as an error.
        if (scan_started_on.length === 0) {
          state.errors = result;
          state.eventErrors.push({
            id: subnetId,
            error: result,
            event: "scan",
          });
        }
      },
    },
    setActive: {
      prepare: (id: Subnet[SubnetMeta.PK] | null) => ({
        meta: {
          model: SubnetMeta.MODEL,
          method: "set_active",
        },
        payload: {
          // Server unsets active item if primary key is not sent.
          params: id === null ? null : { [SubnetMeta.PK]: id },
        },
      }),
      reducer: () => {},
    },
    setActiveError: (
      state: SubnetState,
      action: PayloadAction<SubnetState["errors"]>
    ) => {
      state.active = null;
      state.errors = action.payload;
    },
    setActiveSuccess: (
      state: SubnetState,
      action: PayloadAction<Subnet | null>
    ) => {
      state.active = action.payload ? action.payload[SubnetMeta.PK] : null;
    },
  },
});

export const { actions } = subnetSlice;

export default subnetSlice.reducer;
