import type { PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import type {
  CreateParams,
  ReservedIp,
  ReservedIpState,
  UpdateParams,
} from "./types";
import type { DeleteParams } from "./types/actions";
import { ReservedIpMeta } from "./types/enum";

import type { GenericItemMeta } from "@/app/store/utils/slice";
import {
  generateCommonReducers,
  generateGetReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

const commonReducers = generateCommonReducers<
  ReservedIpState,
  ReservedIpMeta.PK,
  CreateParams,
  UpdateParams
>({ modelName: ReservedIpMeta.MODEL, primaryKey: ReservedIpMeta.PK });

const reservedIpSlice = createSlice({
  name: ReservedIpMeta.MODEL,
  initialState: genericInitialState as ReservedIpState,
  reducers: {
    ...commonReducers,
    ...generateGetReducers<ReservedIpState, ReservedIp, ReservedIpMeta.PK>({
      modelName: ReservedIpMeta.MODEL,
      primaryKey: ReservedIpMeta.PK,
    }),
    createSuccess: (
      state: ReservedIpState,
      action: PayloadAction<ReservedIp>
    ) => {
      commonReducers.createSuccess(state);
      const item = action.payload;
      const index = state.items.findIndex(
        (draftItem: ReservedIp) =>
          draftItem[ReservedIpMeta.PK] === item[ReservedIpMeta.PK]
      );
      if (index !== -1) {
        state.items[index] = item;
      } else {
        state.items.push(item);
      }
    },
    delete: {
      prepare: (params: DeleteParams) => ({
        meta: {
          model: ReservedIpMeta.MODEL,
          method: "delete",
        },
        payload: {
          params,
        },
      }),
      reducer: () => {},
    },
    deleteSuccess: {
      prepare: (params: DeleteParams) => ({
        meta: {
          item: params,
        },
        payload: null,
      }),
      reducer: (
        state: ReservedIpState,
        action: PayloadAction<null, string, GenericItemMeta<DeleteParams>>
      ) => {
        commonReducers.deleteSuccess(state);
        const id = action.meta.item.id;
        const index = state.items.findIndex(
          (draftItem: ReservedIp) => draftItem[ReservedIpMeta.PK] === id
        );

        if (index !== -1) {
          state.items.splice(index, 1);
        }
      },
    },
    updateSuccess: (
      state: ReservedIpState,
      action: PayloadAction<ReservedIp>
    ) => {
      commonReducers.updateSuccess(state);
      const item = action.payload;
      const index = state.items.findIndex(
        (draftItem: ReservedIp) =>
          draftItem[ReservedIpMeta.PK] === item[ReservedIpMeta.PK]
      );
      if (index !== -1) {
        state.items[index] = item;
      }
    },
  },
});

export const { actions } = reservedIpSlice;

export default reservedIpSlice.reducer;
