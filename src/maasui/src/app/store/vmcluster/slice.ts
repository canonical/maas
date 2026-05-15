import { createSlice } from "@reduxjs/toolkit";
import type { PayloadAction } from "@reduxjs/toolkit";

import type {
  DeleteParams,
  VMCluster,
  VMClusterEventError,
  VMClusterState,
} from "./types";
import { VMClusterMeta } from "./types";

import {
  generateCommonReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

const vmClusterSlice = createSlice({
  name: VMClusterMeta.MODEL,
  initialState: {
    ...genericInitialState,
    eventErrors: [],
    physicalClusters: [],
    statuses: {
      deleting: false,
      getting: false,
    },
  } as VMClusterState,
  reducers: {
    ...generateCommonReducers<VMClusterState, VMClusterMeta.PK, void, void>({
      modelName: VMClusterMeta.MODEL,
      primaryKey: VMClusterMeta.PK,
    }),
    cleanup: (state: VMClusterState) => {
      state.errors = null;
      state.eventErrors = [];
      state.saved = false;
      state.saving = false;
    },
    delete: {
      prepare: (params: DeleteParams) => ({
        meta: {
          model: VMClusterMeta.MODEL,
          method: "delete",
        },
        payload: {
          params,
        },
      }),
      reducer: () => {},
    },
    deleteError: (
      state: VMClusterState,
      action: PayloadAction<VMClusterEventError["error"]>
    ) => {
      state.errors = action.payload;
      state.statuses.deleting = false;
      state.eventErrors.push({
        error: action.payload,
        event: "delete",
      });
    },
    deleteStart: (state: VMClusterState) => {
      state.statuses.deleting = true;
    },
    deleteSuccess: (state: VMClusterState) => {
      state.statuses.deleting = false;
    },
    deleteNotify: (
      state: VMClusterState,
      action: PayloadAction<VMCluster[VMClusterMeta.PK]>
    ) => {
      const index = state.items.findIndex(
        (item: VMCluster) => item.id === action.payload
      );
      state.items.splice(index, 1);
    },
    fetch: {
      prepare: () => ({
        meta: {
          cache: true,
          model: VMClusterMeta.MODEL,
          method: "list_by_physical_cluster",
        },
        payload: null,
      }),
      reducer: () => {},
    },
    fetchError: (
      state: VMClusterState,
      action: PayloadAction<VMClusterEventError["error"]>
    ) => {
      state.errors = action.payload;
      state.loading = false;
      state.eventErrors.push({
        error: action.payload,
        event: "fetch",
      });
    },
    fetchStart: (state: VMClusterState) => {
      state.loading = true;
    },
    fetchSuccess: (
      state: VMClusterState,
      action: PayloadAction<VMCluster[][]>
    ) => {
      state.loading = false;
      state.loaded = true;
      // Flatten the items into a single array of vmclusters.
      state.items = action.payload.reduce(
        (flattened, cluster) => flattened.concat(cluster),
        []
      );
      // Store the ids of the vmclusters that are in a physical cluster.
      state.physicalClusters = action.payload.map((cluster) =>
        cluster.map((host) => host[VMClusterMeta.PK])
      );
    },
    get: {
      prepare: (id: VMCluster["id"]) => ({
        meta: {
          model: VMClusterMeta.MODEL,
          method: "get",
        },
        payload: {
          params: { id },
        },
      }),
      reducer: () => {},
    },
    getError: (
      state: VMClusterState,
      action: PayloadAction<VMClusterEventError["error"]>
    ) => {
      state.errors = action.payload;
      state.statuses.getting = false;
      state.eventErrors.push({
        error: action.payload,
        event: "get",
      });
    },
    getStart: (state: VMClusterState) => {
      state.statuses.getting = true;
    },
    getSuccess: (state: VMClusterState, action: PayloadAction<VMCluster>) => {
      state.statuses.getting = false;
      const cluster = action.payload;
      // Add or replace cluster in state.
      const i = state.items.findIndex((item) => item.id === cluster.id);
      if (i !== -1) {
        state.items[i] = cluster;
      } else {
        state.items.push(cluster);
      }
    },
  },
});

export const { actions } = vmClusterSlice;

export default vmClusterSlice.reducer;
