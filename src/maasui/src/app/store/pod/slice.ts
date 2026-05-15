import type { CaseReducer, PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import { PodType } from "./constants";
import { PodMeta } from "./types";
import type {
  CreateParams,
  ComposeParams,
  DeleteParams,
  GetProjectsParams,
  Pod,
  PodProject,
  PodState,
  PollLxdServerParams,
  UpdateParams,
} from "./types";

import { generateStatusHandlers } from "@/app/store/utils";
import type { GenericItemMeta } from "@/app/store/utils";
import {
  generateCommonReducers,
  generateGetReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

export const DEFAULT_STATUSES = {
  composing: false,
  deleting: false,
  refreshing: false,
};

const statusHandlers = generateStatusHandlers<PodState, Pod, PodMeta.PK>(
  PodMeta.PK,
  [
    {
      status: "compose",
      statusKey: "composing",
    },
    {
      status: "delete",
      statusKey: "deleting",
    },
    {
      status: "refresh",
      statusKey: "refreshing",
      success: (state, action) => {
        state.items = state.items.map((item) =>
          item.id === action.payload?.id ? action.payload : item
        );
      },
    },
  ]
);

const podSlice = createSlice({
  name: PodMeta.MODEL,
  initialState: {
    ...genericInitialState,
    active: null,
    projects: {},
    statuses: {},
  } as PodState,
  reducers: {
    ...generateCommonReducers<PodState, PodMeta.PK, CreateParams, UpdateParams>(
      {
        modelName: PodMeta.MODEL,
        primaryKey: PodMeta.PK,
      }
    ),
    clearProjects: (state: PodState) => {
      state.projects = {};
    },
    createNotify: (state: PodState, action) => {
      // In the event that the server erroneously attempts to create an existing machine,
      // due to a race condition etc., ensure we update instead of creating duplicates.
      const existingIdx = state.items.findIndex(
        (draftItem: Pod) => draftItem.id === action.payload.id
      );
      if (existingIdx !== -1) {
        state.items[existingIdx] = action.payload;
      } else {
        state.items.push(action.payload);
        state.statuses[action.payload.id] = DEFAULT_STATUSES;
      }
    },
    compose: {
      prepare: (params: ComposeParams) => ({
        meta: {
          model: PodMeta.MODEL,
          method: "compose",
        },
        payload: {
          params,
        },
      }),
      reducer: () => {},
    },
    composeError: statusHandlers.compose.error as CaseReducer<
      PodState,
      PayloadAction<unknown>
    >,
    composeStart: statusHandlers.compose.start as CaseReducer<
      PodState,
      PayloadAction<unknown>
    >,
    composeSuccess: statusHandlers.compose.success as CaseReducer<
      PodState,
      PayloadAction<unknown>
    >,
    delete: {
      prepare: (params: DeleteParams) => ({
        meta: {
          model: PodMeta.MODEL,
          method: "delete",
        },
        payload: {
          params,
        },
      }),
      reducer: () => {},
    },
    deleteError: statusHandlers.delete.error as CaseReducer<
      PodState,
      PayloadAction<unknown>
    >,
    deleteStart: statusHandlers.delete.start as CaseReducer<
      PodState,
      PayloadAction<unknown>
    >,
    deleteSuccess: statusHandlers.delete.success as CaseReducer<
      PodState,
      PayloadAction<unknown>
    >,
    deleteNotify: (state: PodState, action) => {
      const index = state.items.findIndex(
        (item: Pod) => item.id === action.payload
      );
      state.items.splice(index, 1);
      // Clean up the statuses for model.
      delete state.statuses[action.payload];
    },
    fetchSuccess: (state: PodState, action: PayloadAction<Pod[]>) => {
      state.loading = false;
      state.loaded = true;
      action.payload.forEach((newItem: Pod) => {
        // If the item already exists, update it, otherwise
        // add it to the store.
        const existingIdx = state.items.findIndex(
          (draftItem: Pod) => draftItem.id === newItem.id
        );
        if (existingIdx !== -1) {
          // Don't update the item if it is active so that we don't overwrite
          // the pod details that have already been fetched.
          const hasActive = !!state.active || state.active === 0;
          if (
            !hasActive ||
            (hasActive && state.active !== state.items[existingIdx].id)
          ) {
            state.items[existingIdx] = newItem;
          }
        } else {
          state.items.push(newItem);
          // Set up the statuses for this machine.
          state.statuses[newItem.id] = DEFAULT_STATUSES;
        }
      });
    },
    ...generateGetReducers<PodState, Pod, PodMeta.PK>({
      modelName: PodMeta.MODEL,
      primaryKey: PodMeta.PK,
      defaultStatuses: DEFAULT_STATUSES,
    }),
    getProjects: {
      prepare: (params: GetProjectsParams) => ({
        meta: {
          model: PodMeta.MODEL,
          method: "get_projects",
        },
        payload: {
          params,
        },
      }),
      reducer: () => {},
    },
    getProjectsSuccess: {
      prepare: (
        item: {
          type: Pod["type"];
          power_address: string;
          password?: string;
        },
        payload: PodProject[]
      ) => ({
        meta: {
          item,
        },
        payload,
      }),
      reducer: (
        state: PodState,
        action: PayloadAction<
          PodProject[],
          string,
          GenericItemMeta<GetProjectsParams>
        >
      ) => {
        const address = action.meta.item.power_address;
        if (address) {
          state.projects[address] = action.payload;
        }
      },
    },
    getProjectsError: (
      state: PodState,
      action: PayloadAction<PodState["errors"]>
    ) => {
      state.errors = action.payload;
    },
    pollLxdServer: {
      prepare: (params: PollLxdServerParams) => ({
        meta: {
          model: PodMeta.MODEL,
          method: "get_projects",
          poll: true,
        },
        payload: {
          params: {
            ...params,
            type: PodType.LXD,
          },
        },
      }),
      reducer: () => {},
    },
    pollLxdServerStop: {
      prepare: () => ({
        meta: {
          model: PodMeta.MODEL,
          method: "get_projects",
          pollStop: true,
        },
        payload: null,
      }),
      reducer: () => {},
    },
    pollLxdServerError: (
      state: PodState,
      action: PayloadAction<PodState["errors"]>
    ) => {
      // We deliberately don't stop polling on errors from this action because we
      // continuously use it to check authentication status. When the user is
      // not yet authenticated an error is returned, but the API might respond
      // with other errors (e.g. if you've provided an invalid LXD address).
      state.errors = action.payload;
    },
    pollLxdServerSuccess: {
      prepare: (
        item: {
          type: Pod["type"];
          power_address: string;
        },
        payload: PodProject[]
      ) => ({
        meta: {
          item,
        },
        payload,
      }),
      reducer: (
        state: PodState,
        action: PayloadAction<
          PodProject[],
          string,
          GenericItemMeta<GetProjectsParams>
        >
      ) => {
        state.errors = null;
        const address = action.meta.item.power_address;
        if (address) {
          state.projects[address] = action.payload;
        }
      },
    },
    refresh: {
      prepare: (id: Pod[PodMeta.PK]) => ({
        meta: {
          model: PodMeta.MODEL,
          method: "refresh",
        },
        payload: {
          params: { id },
        },
      }),
      reducer: () => {},
    },
    refreshError: statusHandlers.refresh.error as CaseReducer<
      PodState,
      PayloadAction<unknown>
    >,
    refreshStart: statusHandlers.refresh.start as CaseReducer<
      PodState,
      PayloadAction<unknown>
    >,
    refreshSuccess: statusHandlers.refresh.success as CaseReducer<
      PodState,
      PayloadAction<unknown>
    >,
    setActive: {
      prepare: (id: Pod[PodMeta.PK] | null) => ({
        meta: {
          model: PodMeta.MODEL,
          method: "set_active",
        },
        payload: {
          // Server unsets active pod if primary key (id) is not sent.
          params: id === null ? null : { id },
        },
      }),
      reducer: () => {},
    },
    setActiveError: (
      state: PodState,
      action: PayloadAction<PodState["errors"]>
    ) => {
      state.active = null;
      state.errors = action.payload;
    },
    setActiveSuccess: (state: PodState, action: PayloadAction<Pod | null>) => {
      state.active = action.payload?.id || null;
    },
  },
});

export const { actions } = podSlice;

export default podSlice.reducer;
