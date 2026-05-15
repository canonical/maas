import type { CaseReducer, PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import type { Subnet } from "../subnet/types";

import { VLANMeta } from "./types";
import type {
  ConfigureDHCPParams,
  CreateParams,
  VLAN,
  VLANState,
  UpdateParams,
} from "./types";

import {
  generateCommonReducers,
  generateGetReducers,
  generateStatusHandlers,
  genericInitialState,
  updateErrors,
} from "@/app/store/utils/slice";

export const DEFAULT_STATUSES = {
  configuringDHCP: false,
};

const setErrors = (
  state: VLANState,
  action: PayloadAction<VLANState["errors"]> | null,
  event: string | null
): VLANState =>
  updateErrors<VLANState, VLANMeta.PK>(state, action, event, VLANMeta.PK);

const statusHandlers = generateStatusHandlers<VLANState, VLAN, VLANMeta.PK>(
  VLANMeta.PK,
  [
    {
      status: "configureDHCP",
      statusKey: "configuringDHCP",
    },
  ],
  setErrors
);

const vlanSlice = createSlice({
  name: VLANMeta.MODEL,
  initialState: {
    ...genericInitialState,
    active: null,
    eventErrors: [],
    statuses: {},
  } as VLANState,
  reducers: {
    ...generateCommonReducers<
      VLANState,
      VLANMeta.PK,
      CreateParams,
      UpdateParams
    >({
      modelName: VLANMeta.MODEL,
      primaryKey: VLANMeta.PK,
      setErrors,
    }),
    configureDHCP: {
      prepare: (params: ConfigureDHCPParams) => ({
        meta: {
          model: VLANMeta.MODEL,
          method: "configure_dhcp",
        },
        payload: {
          params,
        },
      }),
      reducer: () => {},
    },
    configureDHCPError: statusHandlers.configureDHCP.error as CaseReducer<
      VLANState,
      PayloadAction<unknown>
    >,
    configureDHCPStart: statusHandlers.configureDHCP.start as CaseReducer<
      VLANState,
      PayloadAction<unknown>
    >,
    configureDHCPSuccess: statusHandlers.configureDHCP.success as CaseReducer<
      VLANState,
      PayloadAction<unknown>
    >,
    createNotify: (state: VLANState, action: PayloadAction<VLAN>) => {
      // In the event that the server erroneously attempts to create an existing
      // VLAN, due to a race condition etc., ensure we update instead of
      // creating duplicates.
      const existingIdx = state.items.findIndex(
        (item) => item.id === action.payload.id
      );
      if (existingIdx !== -1) {
        state.items[existingIdx] = action.payload;
      } else {
        state.items.push(action.payload);
        state.statuses[action.payload.id] = DEFAULT_STATUSES;
      }
    },
    fetchSuccess: (state: VLANState, action: PayloadAction<VLAN[]>) => {
      action.payload.forEach((newItem) => {
        // Add items that don't already exist in the store. Existing items
        // could be VLANDetails so this would overwrite them with the base
        // type. Existing items will be kept up to date via the notify (sync)
        // messages.
        const existing = state.items.find((item) => item.id === newItem.id);
        if (!existing) {
          state.items.push(newItem);
          state.statuses[newItem.id] = DEFAULT_STATUSES;
        }
      });
      state.loading = false;
      state.loaded = true;
    },
    ...generateGetReducers<VLANState, VLAN, VLANMeta.PK>({
      modelName: VLANMeta.MODEL,
      primaryKey: VLANMeta.PK,
      defaultStatuses: DEFAULT_STATUSES,
    }),
    setActive: {
      prepare: (id: VLAN[VLANMeta.PK] | null) => ({
        meta: {
          model: VLANMeta.MODEL,
          method: "set_active",
        },
        payload: {
          // Server unsets active item if primary key is not sent.
          params: id === null ? null : { [VLANMeta.PK]: id },
        },
      }),
      reducer: () => {},
    },
    setActiveError: (
      state: VLANState,
      action: PayloadAction<VLANState["errors"]>
    ) => {
      state.active = null;
      state.errors = action.payload;
    },
    setActiveSuccess: (
      state: VLANState,
      action: PayloadAction<VLAN | null>
    ) => {
      state.active = action.payload ? action.payload[VLANMeta.PK] : null;
    },
  },
  extraReducers: (builder) => {
    // Add the newly created subnet's ID to the corresponding VLAN's subnet_ids array
    builder.addCase(
      "subnet/createNotify",
      (state, action: PayloadAction<Subnet, "subnet/createNotify">) => {
        const { id: subnetId, vlan: vlanId } = action.payload;

        const vlanIndex = state.items.findIndex((item) => item.id === vlanId);

        const vlanExists = vlanIndex !== -1;
        if (vlanExists) {
          state.items[vlanIndex].subnet_ids.push(subnetId);
        }
      }
    );
  },
});

export const { actions } = vlanSlice;

export default vlanSlice.reducer;
