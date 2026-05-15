import type {
  CaseReducer,
  Draft,
  PayloadAction,
  SliceCaseReducers,
} from "@reduxjs/toolkit";

import type { KeysOfUnion } from "@/app/base/types";
import type { ConfigMeta } from "@/app/store/config/types";
import type {
  ControllerMeta,
  ControllerStatus,
} from "@/app/store/controller/types";
import type { DeviceMeta, DeviceStatus } from "@/app/store/device/types";
import type { GeneralMeta } from "@/app/store/general/types";
import type { MachineMeta, MachineStatus } from "@/app/store/machine/types";
import type { MessageMeta } from "@/app/store/message/types";
import type { MsmMeta } from "@/app/store/msm/types/enum";
import type { NodeScriptResultMeta } from "@/app/store/nodescriptresult/types";
import type { PodMeta, PodStatus } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import type { StatusMeta } from "@/app/store/status/types";
import type { SubnetMeta, SubnetStatus } from "@/app/store/subnet/types";
import type { VLANMeta, VLANStatus } from "@/app/store/vlan/types";
import { objectHasKey } from "@/app/utils";

export type GenericItemMeta<I> = GenericMeta & {
  item: I;
};

export type GenericMeta = {
  callId?: string;
  identifier?: number | string;
  item?: unknown;
};

// Get the models that follow the generic shape. The following models are excluded:
// - 'bootresource' does not follow the standard shape.
// - 'config' contains a collection of children without IDs.
// - 'general' has a collection of sub-models that form a different shape.
// - 'messages' not an API model.
// - 'nodescriptresult' returns an object of data rather than an array.
// - 'router' is the react-router state.
// - 'status' is not an API model.
export type CommonStates = Omit<
  RootState,
  | ConfigMeta.MODEL
  | GeneralMeta.MODEL
  | MessageMeta.MODEL
  | MsmMeta.MODEL
  | NodeScriptResultMeta.MODEL
  | StatusMeta.MODEL
  | "router"
>;

// Get the types of the common models. e.g. "DHCPSnippetState".
export type CommonStateTypes = CommonStates[keyof CommonStates];

// Models on the root state that contain statuses.
type StatusStates = Pick<
  RootState,
  | ControllerMeta.MODEL
  | DeviceMeta.MODEL
  | MachineMeta.MODEL
  | PodMeta.MODEL
  | SubnetMeta.MODEL
  | VLANMeta.MODEL
>;

// Types of the statuses for valid models.
type ModelStatuses =
  | ControllerStatus
  | DeviceStatus
  | MachineStatus
  | PodStatus
  | SubnetStatus
  | VLANStatus;

// Models that contain statuses.
type StatusStateTypes = StatusStates[keyof StatusStates];

// Models on the root state that contain event errors.
type EventErrorStates = Pick<
  RootState,
  | ControllerMeta.MODEL
  | DeviceMeta.MODEL
  | MachineMeta.MODEL
  | SubnetMeta.MODEL
  | VLANMeta.MODEL
>;

// Models that contain event errors.
type EventErrorStateTypes = EventErrorStates[keyof EventErrorStates];

/**
 * Search the state type for the matching key for the supplied state.
 */
type SliceState<S extends CommonStates[keyof CommonStates]> = Pick<
  CommonStates,
  {
    [K in keyof CommonStates]: CommonStates[K] extends S ? K : never;
  }[keyof CommonStates]
>;

export const genericInitialState = {
  errors: null,
  items: [],
  loaded: false,
  loading: false,
  saved: false,
  saving: false,
};

/**
 * A method to update the event errors for a model
 * @template S - The model state type e.g. DHCPSnippetState.
 * @template I - A model that is used as an array of items on the provided
 *               state e.g. DHCPSnippet
 * @template K - A model key e.g. "id"
 */
export const updateErrors = <
  S extends EventErrorStateTypes,
  K extends keyof S["items"][0],
>(
  state: S,
  action: {
    payload: S["eventErrors"][0]["error"];
    type: string;
    meta?: GenericItemMeta<S["items"][0]>;
    error?: boolean;
  } | null,
  event: string | null,
  primaryKey: K
): S => {
  // If no action and event have been provided then clean up the errors.
  if (!action && !event) {
    state.eventErrors = [];
    return state;
  }
  const item = action?.meta?.item;
  const items = Array.isArray(item) ? item : [item];
  let newErrors = state.eventErrors as S["eventErrors"][0][];
  items.forEach((item) => {
    const metaId = item ? item[primaryKey] : null;
    // Clean any existing errors that match the event and machine.
    newErrors = newErrors.filter(
      (errorItem) => errorItem.event !== event || errorItem.id !== metaId
    );
    // Set the new error.
    newErrors.push({
      error: action?.payload ?? null,
      event,
      id: metaId,
    } as S["eventErrors"][0]);
  });
  // Replace the event errors with the cleaned/updated list.
  state.eventErrors = newErrors as S["eventErrors"];
  return state;
};

/**
 * A utility to generate a common actions and reducers.
 * @template I - A model that is used as an array of items on the provided
 *               state e.g. DHCPSnippet
 * @template E - The type of the errors for a model's state.
 * @template R - The type of the model's reducers.
 * @param name - The name of the model that matches the name in MAAS.
 * @param primaryKey - The key used to index a model e.g. "system_id".
 * @param setErrors - A function to update eventErrors.
 */
// Defining the return type here means that all the reducers types get lost.

export const generateCommonReducers = <
  S extends CommonStateTypes,
  K extends keyof S["items"][0],
  CreateParams,
  UpdateParams,
>({
  modelName,
  primaryKey,
  setErrors,
}: {
  modelName: keyof SliceState<S>;
  primaryKey: K;
  setErrors?: (
    state: S,
    action: PayloadAction<S["errors"]> | null,
    event: string | null
  ) => S;
}) => {
  return {
    fetch: {
      // Slices that need to pass params to the payload should overwrite this
      // action and reducer.
      prepare: (_unused?: void) => ({
        meta: {
          model: modelName,
          method: "list",
        },
        payload: null,
      }),
      reducer: () => {},
    },
    fetchStart: (state: S) => {
      state.loading = true;
    },
    fetchError: (state: S, action: PayloadAction<S["errors"]>) => {
      state.errors = action.payload;
      if (setErrors) {
        state = setErrors(state, action, "fetch");
      }
      state.loading = false;
    },
    fetchSuccess: (state: S, action: PayloadAction<S["items"]>) => {
      state.loading = false;
      state.loaded = true;
      state.items = action.payload;
    },
    create: {
      prepare: (params: CreateParams) =>
        ({
          meta: {
            model: modelName,
            method: "create",
          },
          payload: {
            params,
          },
        }) as const,
      reducer: () => {},
    },
    createStart: (state: S) => {
      state.saved = false;
      state.saving = true;
    },
    createError: (state: S, action: PayloadAction<S["errors"]>) => {
      state.errors = action.payload;
      if (setErrors) {
        state = setErrors(state, action, "create");
      }
      state.saving = false;
    },
    createSuccess: (state: S) => {
      state.errors = null;
      state.saved = true;
      state.saving = false;
    },
    createNotify: (state: S, action: PayloadAction<S["items"][0]>) => {
      // In the event that the server erroneously attempts to create an
      // existing model, due to a race condition etc., ensure we update instead
      // of creating duplicates.
      const existingIdx = state.items.findIndex(
        (existingItem: S["items"][0]) =>
          existingItem[primaryKey] === action.payload[primaryKey]
      );
      if (existingIdx !== -1) {
        state.items[existingIdx] = action.payload;
      } else {
        // This should just be:
        // state.items.push(action.payload);
        // But because of a typscript issue when using some array methods on
        // generics that extend array unions we instead added the item at the
        // end of the array. This can be updated when the fix for the following
        // issue has been released:
        // https://github.com/microsoft/TypeScript/issues/13995
        state.items[state.items.length] = action.payload;
      }
    },
    update: {
      prepare: (params: UpdateParams) => ({
        meta: {
          model: modelName,
          method: "update",
        },
        payload: {
          params,
        },
      }),
      reducer: () => {},
    },
    updateStart: (state: S) => {
      state.saved = false;
      state.saving = true;
    },
    updateError: (state: S, action: PayloadAction<S["errors"]>) => {
      state.errors = action.payload;
      if (setErrors) {
        state = setErrors(state, action, "update");
      }
      state.saving = false;
    },
    updateSuccess: (state: S) => {
      state.errors = null;
      state.saved = true;
      state.saving = false;
    },
    updateNotify: (state: S, action: PayloadAction<S["items"][0]>) => {
      state.items.forEach((item: S["items"][0], i: number) => {
        if (item[primaryKey] === action.payload[primaryKey]) {
          state.items[i] = action.payload;
        }
      });
    },
    delete: {
      // Slices that use a different key e.g. system_id should overwrite this
      // action and reducer.
      prepare: (id: S["items"][0][K]) => ({
        meta: {
          model: modelName,
          method: "delete",
        },
        payload: {
          params: {
            id,
          },
        },
      }),
      reducer: () => {},
    },
    deleteStart: (state: S) => {
      state.saved = false;
      state.saving = true;
    },
    deleteError: (state: S, action: PayloadAction<S["errors"]>) => {
      state.errors = action.payload;
      if (setErrors) {
        state = setErrors(state, action, "delete");
      }
      state.saving = false;
    },
    deleteSuccess: (state: S) => {
      state.errors = null;
      state.saved = true;
      state.saving = false;
    },
    deleteNotify: (state: S, action: PayloadAction<S["items"][0][K]>) => {
      const index = state.items.findIndex(
        (item: S["items"][0]) => item[primaryKey] === action.payload
      );
      state.items.splice(index, 1);
    },
    cleanup(state: S, _action: PayloadAction) {
      state.errors = null;
      if (setErrors) {
        state = setErrors(state, null, null);
      }
      state.saved = false;
      state.saving = false;
    },
  };
};

/**
 * The handlers for a status.
 * @template S - A model that includes status e.g. Machine.
 * @template I - A model that is used as an array of items on the provided
 *               state e.g. DHCPSnippet
 */
export type StatusHandlers<
  S extends StatusStateTypes,
  I extends S["items"][0],
  // alternative success payload type
  A = void,
> = {
  method?: string;
  status: string;
  statusKey: KeysOfUnion<ModelStatuses>;
  // The handler for when there is an error.
  error?: CaseReducer<
    S,
    PayloadAction<S["errors"], string, GenericItemMeta<I>>
  >;
  // The handler for when the action has started.
  start?: CaseReducer<S, PayloadAction<I, string, GenericItemMeta<I>>>;
  // The handler for when the action has successfully completed.
  success?: CaseReducer<S, PayloadAction<A | I, string, GenericItemMeta<I>>>;
};

/**
 * A utility to generate reducers and actions to append to a slice.
 * @template S - A model that includes status e.g. Machine.
 * @template I - A model that is used as an array of items on the provided
 *               state e.g. DHCPSnippet
 * @template K - A model key e.g. "id"
 * @param primaryKey - The key used to index a model e.g. "id"
 *                            or "system_id".
 * @param handlers - A collection of status handlers.
 * @param setErrors - A function to update eventErrors.
 */
export const generateStatusHandlers = <
  S extends StatusStateTypes,
  I extends S["items"][0],
  // A model key as a reference to the supplied state item.
  K extends keyof I,
  // optional alternative success payload type
  A = void,
>(
  primaryKey: K,
  handlers: StatusHandlers<S, I, A>[],
  setErrors?: (
    state: Draft<S>,
    action: PayloadAction<S["errors"]>,
    event: string
  ) => Draft<S>
): Record<string, SliceCaseReducers<S>> =>
  handlers.reduce<Record<string, SliceCaseReducers<S>>>(
    (collection, status) => {
      collection[status.status] = {
        // The handler for when the action has started.
        start: {
          prepare: ({ item, payload }) => ({
            meta: {
              item,
            },
            payload,
          }),
          reducer: (
            state: Draft<S>,
            action: PayloadAction<I, string, GenericItemMeta<I>>
          ) => {
            // Call the reducer handler if supplied.
            status.start && status.start(state, action);
            if (action.meta.item) {
              const statusItem =
                state.statuses[String(action.meta.item[primaryKey])];
              const statusKey = status.statusKey;
              if (objectHasKey(statusKey as string, statusItem)) {
                statusItem[statusKey] = true;
              }
            }
          },
        },
        // The handler for when the action has successfully completed.
        success: {
          prepare: ({ item, payload }) => ({
            meta: {
              item,
            },
            payload,
          }),
          reducer: (
            state: Draft<S>,
            action: PayloadAction<A | I, string, GenericItemMeta<I>>
          ) => {
            // Call the reducer handler if supplied.
            status.success && status.success(state, action);
            if (action.meta.item) {
              const statusItem =
                state.statuses[String(action.meta.item[primaryKey])];
              // Sometimes the server will respond with "machine/deleteNotify"
              // before "machine/deleteSuccess", which removes the machine
              // system_id from statuses so check the item exists, to be safe.
              const statusKey = status.statusKey;
              if (objectHasKey(statusKey as string, statusItem)) {
                statusItem[statusKey] = false;
              }
            }
          },
        },
        // The handler for when there is an error.
        error: {
          prepare: ({ item, payload }) => ({
            meta: {
              item,
            },
            payload,
          }),
          reducer: (
            state: Draft<S>,
            action: PayloadAction<S["errors"], string, GenericItemMeta<I>>
          ) => {
            // Call the reducer handler if supplied.
            status.error && status.error(state, action);
            state.errors = action.payload;
            if (setErrors) {
              state = setErrors(state, action, status.status);
            }
            if (action.meta.item) {
              const statusItem =
                state.statuses[String(action.meta.item[primaryKey])];
              const statusKey = status.statusKey;
              if (objectHasKey(statusKey as string, statusItem)) {
                statusItem[statusKey] = false;
              }
            }
          },
        },
      };
      return collection;
    },
    {}
  );

export const generateGetReducers = <
  S extends CommonStateTypes | EventErrorStateTypes | StatusStateTypes,
  T extends S["items"][0],
  K extends keyof T,
>({
  modelName,
  primaryKey,
  defaultStatuses,
  setErrors,
}: {
  modelName: keyof SliceState<S>;
  primaryKey: K;
  defaultStatuses?: S extends StatusStateTypes
    ? S["statuses"][T[K] & keyof S["statuses"]]
    : never;
  setErrors?: (
    state: S,
    action: PayloadAction<S["errors"]> | null,
    event: string | null
  ) => S;
}) => {
  return {
    get: {
      prepare: (id: T[K]) => ({
        meta: {
          model: modelName,
          method: "get",
        },
        payload: {
          params: {
            [primaryKey]: id,
          },
        },
      }),
      reducer: () => {},
    },
    getStart: (state: S) => {
      state.loading = true;
    },
    getError: (state: S, action: PayloadAction<S["errors"]>) => {
      state.errors = action.payload;
      if (setErrors) {
        state = setErrors(state, action, "get");
      }
      state.loading = false;
      state.saving = false;
    },
    getSuccess: (state: S, action: PayloadAction<T>) => {
      const item = action.payload;
      const index = (state.items as T[]).findIndex(
        (draftItem: T) => draftItem[primaryKey] === item[primaryKey]
      );
      if (index !== -1) {
        state.items[index] = item;
      } else {
        (state.items as T[]).push(item);
        if ("statuses" in state && defaultStatuses) {
          (state.statuses as StatusStateTypes["statuses"])[
            item[primaryKey] as keyof StatusStateTypes["statuses"]
          ] = defaultStatuses;
        }
      }
      state.loading = false;
      state.saving = false;
    },
  };
};
