import type { PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import type { GenericItemMeta } from "../utils";

import { NodeDeviceMeta } from "./types";
import type { NodeDevice, NodeDeviceState } from "./types";

import type { Node } from "@/app/store/types/node";
import {
  generateCommonReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

type ItemMeta = {
  system_id: Node["system_id"];
};

const nodeDeviceSlice = createSlice({
  name: NodeDeviceMeta.MODEL,
  initialState: genericInitialState as NodeDeviceState,
  reducers: {
    ...generateCommonReducers<NodeDeviceState, NodeDeviceMeta.PK, void, void>({
      modelName: NodeDeviceMeta.MODEL,
      primaryKey: NodeDeviceMeta.PK,
    }),
    getByNodeId: {
      prepare: (nodeID: Node["system_id"]) => ({
        meta: {
          model: NodeDeviceMeta.MODEL,
          method: "list",
          nocache: true,
        },
        payload: {
          params: {
            system_id: nodeID,
          },
        },
      }),
      reducer: () => {
        // no state changes needed
      },
    },
    getByNodeIdStart: (
      state: NodeDeviceState,
      _action: PayloadAction<null>
    ) => {
      state.loading = true;
    },
    getByNodeIdError: (
      state: NodeDeviceState,
      action: PayloadAction<NodeDeviceState["errors"]>
    ) => {
      state.errors = action.payload;
      state.loading = false;
      state.saving = false;
    },
    getByNodeIdSuccess: {
      prepare: (nodeID: Node["system_id"], nodeDevices: NodeDevice[]) => ({
        meta: {
          item: {
            system_id: nodeID,
          },
        },
        payload: nodeDevices,
      }),
      reducer: (
        state: NodeDeviceState,
        action: PayloadAction<NodeDevice[], string, GenericItemMeta<ItemMeta>>
      ) => {
        action.payload.forEach((result) => {
          const i = state.items.findIndex(
            (draftItem: NodeDevice) => draftItem.id === result.id
          );
          if (i !== -1) {
            state.items[i] = result;
          } else {
            state.items.push(result);
          }
        });
        state.loading = false;
        state.loaded = true;
      },
    },
  },
});

export const { actions } = nodeDeviceSlice;

export default nodeDeviceSlice.reducer;
