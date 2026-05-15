import type { PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import type { Node } from "../types/node";
import type { GenericItemMeta } from "../utils";

import { ScriptResultMeta } from "./types";
import type {
  PartialScriptResult,
  ScriptResult,
  ScriptResultDataType,
  ScriptResultState,
} from "./types";

import {
  generateCommonReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

type HistoryItemMeta = {
  id: number;
};

type LogsItemMeta = HistoryItemMeta & { data_type: ScriptResultDataType };

const scriptResultSlice = createSlice({
  name: ScriptResultMeta.MODEL,
  initialState: {
    ...genericInitialState,
    history: {},
    logs: null,
  } as ScriptResultState,
  reducers: {
    ...generateCommonReducers<
      ScriptResultState,
      ScriptResultMeta.PK,
      void,
      void
    >({
      modelName: ScriptResultMeta.MODEL,
      primaryKey: ScriptResultMeta.PK,
    }),
    get: {
      prepare: (id: ScriptResult[ScriptResultMeta.PK]) => ({
        meta: {
          model: "noderesult",
          method: "get",
        },
        payload: {
          params: {
            id,
          },
        },
      }),
      reducer: () => {
        // no state changes needed
      },
    },
    getStart: (state: ScriptResultState, _action: PayloadAction<null>) => {
      state.loading = true;
    },
    getError: (
      state: ScriptResultState,
      action: PayloadAction<ScriptResultState["errors"]>
    ) => {
      state.errors = action.payload;
      state.loading = false;
    },
    getSuccess: (
      state: ScriptResultState,
      action: PayloadAction<ScriptResult>
    ) => {
      const result = action.payload;
      const i = state.items.findIndex(
        (draftItem: ScriptResult) => draftItem.id === result.id
      );
      if (i !== -1) {
        state.items[i] = result;
      } else {
        state.items.push(result);
      }
      if (!(result.id in state.history)) {
        state.history[result.id] = [];
      }
      state.loading = false;
    },
    getByNodeId: {
      prepare: (nodeID: Node["system_id"]) => ({
        meta: {
          model: "noderesult",
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
      state: ScriptResultState,
      _action: PayloadAction<null>
    ) => {
      state.loading = true;
    },
    getByNodeIdError: (
      state: ScriptResultState,
      action: PayloadAction<ScriptResultState["errors"]>
    ) => {
      state.errors = action.payload;
      state.loading = false;
      state.saving = false;
    },
    getByNodeIdSuccess: {
      prepare: (
        system_id: Node["system_id"],
        scriptResults: ScriptResult[]
      ) => ({
        meta: {
          item: {
            system_id,
          },
        },
        payload: scriptResults,
      }),
      reducer: (
        state: ScriptResultState,
        action: PayloadAction<
          ScriptResult[],
          string,
          GenericItemMeta<{
            system_id: Node["system_id"];
          }>
        >
      ) => {
        action.payload.forEach((result) => {
          const i = state.items.findIndex(
            (draftItem: ScriptResult) => draftItem.id === result.id
          );
          if (i !== -1) {
            state.items[i] = result;
          } else {
            state.items.push(result);
          }
          state.history[result.id] = [];
        });
        state.loading = false;
        state.loaded = true;
      },
    },
    getHistory: {
      prepare: (id: ScriptResult[ScriptResultMeta.PK]) => ({
        meta: {
          model: "noderesult",
          method: "get_history",
          nocache: true,
        },
        payload: {
          params: {
            id,
          },
        },
      }),
      reducer: () => {
        // no state changes needed
      },
    },
    getHistoryStart: (
      state: ScriptResultState,
      _action: PayloadAction<null>
    ) => {
      state.loading = true;
    },
    getHistoryError: (
      state: ScriptResultState,
      action: PayloadAction<ScriptResultState["errors"]>
    ) => {
      state.errors = action.payload;
      state.loading = false;
      state.saving = false;
    },
    getHistorySuccess: {
      prepare: (
        id: ScriptResult[ScriptResultMeta.PK],
        scriptResults: PartialScriptResult[]
      ) => ({
        meta: {
          item: {
            id,
          },
        },
        payload: scriptResults,
      }),
      reducer: (
        state: ScriptResultState,
        action: PayloadAction<
          PartialScriptResult[],
          string,
          GenericItemMeta<HistoryItemMeta>
        >
      ) => {
        state.history[action.meta.item.id] = action.payload;
        state.loading = false;
        state.loaded = true;
      },
    },
    getLogs: {
      prepare: (
        id: ScriptResult[ScriptResultMeta.PK],
        type: ScriptResultDataType
      ) => ({
        meta: {
          model: "noderesult",
          method: "get_result_data",
          nocache: true,
        },
        payload: {
          params: {
            id,
            data_type: type,
          },
        },
      }),
      reducer: () => {
        // no state changes needed
      },
    },
    getLogsStart: (state: ScriptResultState, _action: PayloadAction<null>) => {
      state.loading = true;
    },
    getLogsError: (
      state: ScriptResultState,
      action: PayloadAction<ScriptResultState["errors"]>
    ) => {
      state.errors = action.payload;
      state.loading = false;
      state.saving = false;
    },
    getLogsSuccess: {
      prepare: (
        id: ScriptResult[ScriptResultMeta.PK],
        logType: ScriptResultDataType,
        payload: string
      ) => ({
        meta: {
          item: {
            id,
            data_type: logType,
          },
        },
        payload,
      }),
      reducer: (
        state: ScriptResultState,
        action: PayloadAction<string, string, GenericItemMeta<LogsItemMeta>>
      ) => {
        if (!state.logs) {
          state.logs = {};
        }
        const { id, data_type } = action.meta.item;
        if (!state.logs[id]) {
          state.logs[id] = {};
        }
        state.logs[id][data_type] = action.payload;
        state.loading = false;
        state.loaded = true;
      },
    },
  },
  extraReducers: (builder) => {
    builder.addCase(
      "noderesult/createNotify",
      (
        state,
        action: PayloadAction<ScriptResult, "noderesult/createNotify">
      ) => {
        const existingIdx = state.items.findIndex(
          (existingItem) => existingItem.id === action.payload.id
        );
        if (existingIdx !== -1) {
          state.items[existingIdx] = action.payload;
        } else {
          state.items.push(action.payload);
        }
      }
    );
    builder.addCase(
      "noderesult/updateNotify",
      (
        state,
        action: PayloadAction<ScriptResult, "noderesult/updateNotify">
      ) => {
        const existingIdx = state.items.findIndex(
          (existingItem) => existingItem.id === action.payload.id
        );
        if (existingIdx !== -1) {
          state.items[existingIdx] = action.payload;
        } else {
          state.items.push(action.payload);
        }
      }
    );
  },
});

export const { actions } = scriptResultSlice;

export default scriptResultSlice.reducer;
