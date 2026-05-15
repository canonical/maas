import type { Slice, PayloadAction, CaseReducer } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import { PodMeta } from "@/app/store/pod/types";
import type { Pod, PodState } from "@/app/store/pod/types";
import { TokenMeta } from "@/app/store/token/types";
import type { TokenState } from "@/app/store/token/types";
import {
  generateCommonReducers,
  generateStatusHandlers,
  genericInitialState,
} from "@/app/store/utils/slice";
import * as factory from "@/testing/factories";

describe("slice", () => {
  describe("base reducers", () => {
    let slice: Slice;

    beforeEach(() => {
      slice = createSlice({
        name: TokenMeta.MODEL,
        initialState: genericInitialState as TokenState,
        reducers: generateCommonReducers<TokenState, TokenMeta.PK, void, void>({
          modelName: TokenMeta.MODEL,
          primaryKey: TokenMeta.PK,
        }),
      });
    });

    it("returns the initial state", () => {
      expect(slice.reducer(undefined, { type: "" })).toEqual({
        errors: null,
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      });
    });

    it("reduces fetchStart", () => {
      expect(slice.reducer(undefined, slice.actions.fetchStart(null))).toEqual({
        errors: null,
        items: [],
        loaded: false,
        loading: true,
        saved: false,
        saving: false,
      });
    });

    it("reduces fetchSuccess", () => {
      const tokens = [factory.token()];
      const tokenState = factory.tokenState({
        items: [],
        loading: true,
      });
      expect(
        slice.reducer(tokenState, slice.actions.fetchSuccess(tokens))
      ).toEqual({
        errors: null,
        loading: false,
        loaded: true,
        saved: false,
        saving: false,
        items: tokens,
      });
    });

    it("reduces fetchError", () => {
      const tokenState = factory.tokenState();
      expect(
        slice.reducer(
          tokenState,
          slice.actions.fetchError("Could not fetch tokens")
        )
      ).toEqual({
        errors: "Could not fetch tokens",
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      });
    });

    it("reduces createStart", () => {
      const tokenState = factory.tokenState({ saved: true });
      expect(
        slice.reducer(tokenState, slice.actions.createStart(null))
      ).toEqual({
        errors: null,
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: true,
      });
    });

    it("reduces createError", () => {
      const tokenState = factory.tokenState();
      expect(
        slice.reducer(
          tokenState,
          slice.actions.createError({ name: "Token name already exists" })
        )
      ).toEqual({
        errors: { name: "Token name already exists" },
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      });
    });

    it("reduces createNotify", () => {
      const tokens = [factory.token({ id: 1 })];
      const newToken = factory.token({ id: 2 });
      const tokenState = factory.tokenState({
        items: tokens,
      });

      expect(
        slice.reducer(tokenState, slice.actions.createNotify(newToken))
      ).toEqual({
        errors: null,
        items: [...tokens, newToken],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      });
    });

    it("reduces updateStart", () => {
      const tokenState = factory.tokenState({ saved: true });
      expect(
        slice.reducer(tokenState, slice.actions.updateStart(null))
      ).toEqual({
        errors: null,
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: true,
      });
    });

    it("reduces updateError", () => {
      const tokenState = factory.tokenState();
      expect(
        slice.reducer(
          tokenState,
          slice.actions.updateError({ name: "Token name already exists" })
        )
      ).toEqual({
        errors: { name: "Token name already exists" },
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      });
    });

    it("reduces updateNotify", () => {
      const newToken = factory.token({ id: 1, key: "new-key" });
      const tokenState = factory.tokenState({
        items: [factory.token({ id: 1, key: "old-key" })],
      });
      expect(
        slice.reducer(tokenState, slice.actions.updateNotify(newToken))
      ).toEqual({
        errors: null,
        items: [newToken],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      });
    });

    it("reduces deleteStart", () => {
      const tokens = [factory.token({ id: 1 })];
      const tokenState = factory.tokenState({
        items: tokens,
      });
      expect(
        slice.reducer(tokenState, slice.actions.deleteStart(null))
      ).toEqual({
        errors: null,
        items: tokens,
        loaded: false,
        loading: false,
        saved: false,
        saving: true,
      });
    });

    it("reduces deleteSuccess", () => {
      const tokens = [factory.token({ id: 1 })];
      const tokenState = factory.tokenState({
        items: tokens,
      });
      expect(
        slice.reducer(tokenState, slice.actions.deleteSuccess(null))
      ).toEqual({
        errors: null,
        items: tokens,
        loaded: false,
        loading: false,
        saved: true,
        saving: false,
      });
    });

    it("reduces deleteError", () => {
      const tokens = [factory.token({ id: 1 })];
      const tokenState = factory.tokenState({
        items: tokens,
      });
      expect(
        slice.reducer(
          tokenState,
          slice.actions.deleteError("Token cannot be deleted")
        )
      ).toEqual({
        errors: "Token cannot be deleted",
        items: tokens,
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      });
    });

    it("reduces deleteNotify", () => {
      const tokens = [factory.token({ id: 1 }), factory.token({ id: 2 })];
      const tokenState = factory.tokenState({
        items: tokens,
      });
      expect(slice.reducer(tokenState, slice.actions.deleteNotify(1))).toEqual({
        errors: null,
        items: [tokens[1]],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      });
    });
  });

  describe("additional reducers", () => {
    it("can reduce a custom reducer", () => {
      const slice = createSlice({
        name: TokenMeta.MODEL,
        initialState: genericInitialState as TokenState,
        reducers: {
          ...generateCommonReducers<TokenState, TokenMeta.PK, void, void>({
            modelName: TokenMeta.MODEL,
            primaryKey: TokenMeta.PK,
          }),
          custom: (state: TokenState, _action: PayloadAction<undefined>) => {
            state.errors = "small potato";
          },
        },
      });

      const tokenState = factory.tokenState();
      expect(slice.reducer(tokenState, slice.actions.custom())).toEqual({
        errors: "small potato",
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      });
    });

    it("can overwrite a base reducer", () => {
      const slice = createSlice({
        name: TokenMeta.MODEL,
        initialState: genericInitialState as TokenState,
        reducers: {
          ...generateCommonReducers<TokenState, TokenMeta.PK, void, void>({
            modelName: TokenMeta.MODEL,
            primaryKey: TokenMeta.PK,
          }),
          fetchError: (state: TokenState, action: PayloadAction<string>) => {
            state.errors = `${action.payload} potato`;
          },
        },
      });
      const tokenState = factory.tokenState();
      expect(
        slice.reducer(tokenState, slice.actions.fetchError("small"))
      ).toEqual({
        errors: "small potato",
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      });
    });
  });

  describe("base actions", () => {
    let slice: Slice;

    beforeEach(() => {
      slice = createSlice({
        name: TokenMeta.MODEL,
        initialState: genericInitialState as TokenState,
        reducers: generateCommonReducers<TokenState, TokenMeta.PK, void, void>({
          modelName: TokenMeta.MODEL,
          primaryKey: TokenMeta.PK,
        }),
      });
    });

    it("can create an action for fetching tokens", () => {
      expect(slice.actions.fetch(null)).toEqual({
        type: "token/fetch",
        meta: {
          model: TokenMeta.MODEL,
          method: "list",
        },
        payload: null,
      });
    });

    it("can create an action for creating a token", () => {
      expect(
        slice.actions.create({ name: "token1", description: "a token" })
      ).toEqual({
        type: "token/create",
        meta: {
          model: TokenMeta.MODEL,
          method: "create",
        },
        payload: {
          params: {
            name: "token1",
            description: "a token",
          },
        },
      });
    });

    it("can create an action for updating a token", () => {
      expect(
        slice.actions.update({ name: "token1", description: "a token" })
      ).toEqual({
        type: "token/update",
        meta: {
          model: TokenMeta.MODEL,
          method: "update",
        },
        payload: {
          params: {
            name: "token1",
            description: "a token",
          },
        },
      });
    });

    it("can create an action for deleting a token", () => {
      expect(slice.actions.delete(808)).toEqual({
        type: "token/delete",
        meta: {
          model: TokenMeta.MODEL,
          method: "delete",
        },
        payload: {
          params: {
            id: 808,
          },
        },
      });
    });
  });

  describe("status reducers", () => {
    let slice: Slice;

    beforeEach(() => {
      const statusHandlers = generateStatusHandlers<PodState, Pod, PodMeta.PK>(
        PodMeta.PK,
        [
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
      slice = createSlice({
        name: PodMeta.MODEL,
        initialState: {
          ...genericInitialState,
          active: null,
          projects: {},
          statuses: {},
        } as PodState,
        reducers: {
          ...generateCommonReducers<PodState, PodMeta.PK, void, void>({
            modelName: PodMeta.MODEL,
            primaryKey: PodMeta.PK,
          }),
          refreshStart: statusHandlers.refresh.start as CaseReducer<
            PodState,
            PayloadAction<unknown>
          >,
          refreshSuccess: statusHandlers.refresh.success as CaseReducer<
            PodState,
            PayloadAction<unknown>
          >,
          refreshError: statusHandlers.refresh.error as CaseReducer<
            PodState,
            PayloadAction<unknown>
          >,
        },
      });
    });

    it("reduces the start action", () => {
      const pods = [factory.pod({ id: 1 })];
      const podState = factory.podState({
        items: pods,
        statuses: {
          1: factory.podStatus({ refreshing: false }),
        },
      });

      expect(
        slice.reducer(podState, slice.actions.refreshStart({ item: pods[0] }))
      ).toEqual(
        factory.podState({
          items: pods,
          statuses: { 1: factory.podStatus({ refreshing: true }) },
        })
      );
    });

    it("reduces the success action", () => {
      const pods = [factory.pod({ id: 1, cpu_speed: 100 })];
      const updatedPod = factory.pod({ id: 1, cpu_speed: 100 });
      const podState = factory.podState({
        items: pods,
        statuses: {
          1: factory.podStatus({ refreshing: true }),
        },
      });

      expect(
        slice.reducer(
          podState,
          slice.actions.refreshSuccess({ item: pods[0], payload: updatedPod })
        )
      ).toEqual(
        factory.podState({
          items: [updatedPod],
          statuses: { 1: factory.podStatus({ refreshing: false }) },
        })
      );
    });

    it("reduces the error action", () => {
      const pods = [factory.pod({ id: 1, cpu_speed: 100 })];
      const podState = factory.podState({
        items: pods,
        statuses: {
          1: factory.podStatus({ refreshing: true }),
        },
      });

      expect(
        slice.reducer(
          podState,
          slice.actions.refreshError({
            item: pods[0],
            payload: "You dun goofed",
          })
        )
      ).toEqual(
        factory.podState({
          errors: "You dun goofed",
          items: pods,
          statuses: { 1: factory.podStatus({ refreshing: false }) },
        })
      );
    });
  });
});
