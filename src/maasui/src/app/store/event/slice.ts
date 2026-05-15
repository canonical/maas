import type { PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import { EventMeta } from "./types";
import type { EventRecord, EventState } from "./types";

import {
  generateCommonReducers,
  genericInitialState,
} from "@/app/store/utils/slice";

const eventSlice = createSlice({
  name: EventMeta.MODEL,
  initialState: genericInitialState as EventState,
  reducers: {
    ...generateCommonReducers<EventState, EventMeta.PK, void, void>({
      modelName: EventMeta.MODEL,
      primaryKey: EventMeta.PK,
    }),
    fetch: {
      prepare: (
        node_id: EventRecord["node_id"],
        limit?: number | null,
        start?: number | null
      ) => ({
        meta: {
          model: EventMeta.MODEL,
          method: "list",
          // This list method fetches events by node ID, so don't prevent
          // fetching multiple times.
          nocache: true,
        },
        payload: {
          params: {
            node_id,
            // Only send the params that are provided.
            ...(limit || limit === 0 ? { limit } : {}),
            ...(start || start === 0 ? { start } : {}),
          },
        },
      }),
      reducer: () => {},
    },
    fetchSuccess: (
      state: EventState,
      action: PayloadAction<EventState["items"]>
    ) => {
      state.loading = false;
      state.loaded = true;
      // Events are fetch by node ID and can be limited/paginated, so each time
      // events are fetch they need to be appended to the current list of events
      // instead of replacing the events.
      action.payload.forEach((nodeEvent) => {
        // Prevent duplicates:
        if (!state.items.find(({ id }) => id === nodeEvent.id)) {
          state.items.push(nodeEvent);
        }
      });
    },
  },
});

export const { actions } = eventSlice;

export default eventSlice.reducer;
