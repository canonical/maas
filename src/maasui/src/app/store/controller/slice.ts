import type { CaseReducer, PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import type {
  Action,
  Controller,
  ControllerState,
  ControllerStatus,
  CreateParams,
  UpdateParams,
} from "./types";
import { ControllerMeta } from "./types";
import type {
  GetSummaryXmlParams,
  GetSummaryYamlParams,
} from "./types/actions";
import type { ImageSyncStatuses } from "./types/base";

import type {
  BaseNodeActionParams,
  SetZoneParams,
  TestParams,
} from "@/app/store/types/node";
import { NodeActions } from "@/app/store/types/node";
import type { GenericItemMeta, StatusHandlers } from "@/app/store/utils/slice";
import {
  generateCommonReducers,
  generateGetReducers,
  generateStatusHandlers,
  genericInitialState,
  updateErrors,
} from "@/app/store/utils/slice";
import { kebabToCamelCase } from "@/app/utils";

type CheckImagesItem = {
  [ControllerMeta.PK]: Controller[ControllerMeta.PK];
};

export const ACTIONS: Action[] = [
  {
    name: NodeActions.DELETE,
    status: "deleting",
  },
  {
    name: "get-summary-xml",
    status: "gettingSummaryXml",
  },
  {
    name: "get-summary-yaml",
    status: "gettingSummaryYaml",
  },
  {
    name: NodeActions.IMPORT_IMAGES,
    status: "importingImages",
  },
  {
    name: NodeActions.OFF,
    status: "turningOff",
  },
  {
    name: NodeActions.ON,
    status: "turningOn",
  },
  {
    name: NodeActions.OVERRIDE_FAILED_TESTING,
    status: "overridingFailedTesting",
  },
  {
    name: NodeActions.SET_ZONE,
    status: "settingZone",
  },
  {
    name: NodeActions.TEST,
    status: "testing",
  },
];

export const DEFAULT_STATUSES: ControllerStatus = {
  checkingImages: false,
  deleting: false,
  gettingSummaryXml: false,
  gettingSummaryYaml: false,
  importingImages: false,
  overridingFailedTesting: false,
  settingZone: false,
  testing: false,
  turningOff: false,
  turningOn: false,
};

const setErrors = (
  state: ControllerState,
  action: PayloadAction<ControllerState["errors"]> | null,
  event: string | null
): ControllerState =>
  updateErrors<ControllerState, ControllerMeta.PK>(
    state,
    action,
    event,
    ControllerMeta.PK
  );

const statusHandlers = generateStatusHandlers<
  ControllerState,
  Controller,
  ControllerMeta.PK
>(
  ControllerMeta.PK,
  ACTIONS.map((action) => {
    const handler: StatusHandlers<ControllerState, Controller> = {
      status: kebabToCamelCase(action.name),
      method: "action",
      statusKey: action.status,
    };
    return handler;
  }),
  setErrors
);

const controllerSlice = createSlice({
  name: ControllerMeta.MODEL,
  initialState: {
    ...genericInitialState,
    active: null,
    eventErrors: [],
    imageSyncStatuses: {},
    selected: [],
    statuses: {},
  } as ControllerState,
  reducers: {
    ...generateCommonReducers<
      ControllerState,
      ControllerMeta.PK,
      CreateParams,
      UpdateParams
    >({
      modelName: ControllerMeta.MODEL,
      primaryKey: ControllerMeta.PK,
      setErrors,
    }),
    checkImages: {
      prepare: (ids: Controller[ControllerMeta.PK][]) => ({
        meta: {
          model: ControllerMeta.MODEL,
          method: "check_images",
        },
        payload: {
          params: ids.map((id) => ({ [ControllerMeta.PK]: id })),
        },
      }),
      reducer: () => {},
    },
    checkImagesError: {
      prepare: (item: CheckImagesItem[], error: ControllerState["errors"]) => ({
        meta: {
          item,
        },
        payload: error,
      }),
      reducer: (
        state: ControllerState,
        action: PayloadAction<
          ControllerState["errors"],
          string,
          GenericItemMeta<CheckImagesItem[]>
        >
      ) => {
        state = setErrors(state, action, "checkImages");
        action.meta.item.forEach(({ system_id }) => {
          if (system_id in state.statuses) {
            state.statuses[system_id].checkingImages = false;
          }
        });
      },
    },
    checkImagesStart: {
      prepare: (item: CheckImagesItem[]) => ({
        meta: {
          item,
        },
        payload: null,
      }),
      reducer: (
        state: ControllerState,
        action: PayloadAction<null, string, GenericItemMeta<CheckImagesItem[]>>
      ) => {
        action.meta.item.forEach(({ system_id }) => {
          if (system_id in state.statuses) {
            state.statuses[system_id].checkingImages = true;
          }
        });
      },
    },
    checkImagesSuccess: {
      prepare: (item: CheckImagesItem[], payload: ImageSyncStatuses) => ({
        meta: {
          item,
        },
        payload,
      }),
      reducer: (
        state: ControllerState,
        action: PayloadAction<
          ImageSyncStatuses,
          string,
          GenericItemMeta<CheckImagesItem[]>
        >
      ) => {
        // Insert or overwrite statuses for the controllers in this request.
        state.imageSyncStatuses = {
          ...state.imageSyncStatuses,
          ...action.payload,
        };
        action.meta.item.forEach(({ system_id }) => {
          if (system_id in state.statuses) {
            state.statuses[system_id].checkingImages = false;
          }
        });
      },
    },
    createNotify: (
      state: ControllerState,
      action: PayloadAction<Controller>
    ) => {
      // In the event that the server erroneously attempts to create an existing controller,
      // due to a race condition etc., ensure we update instead of creating duplicates.
      const existingIdx = state.items.findIndex(
        (draftItem: Controller) =>
          draftItem.system_id === action.payload.system_id
      );
      if (existingIdx !== -1) {
        state.items[existingIdx] = action.payload;
      } else {
        state.items.push(action.payload);
        state.statuses[action.payload.system_id] = DEFAULT_STATUSES;
      }
    },
    delete: {
      prepare: (params: BaseNodeActionParams) => ({
        meta: {
          model: ControllerMeta.MODEL,
          method: "action",
        },
        payload: {
          params: {
            action: NodeActions.DELETE,
            extra: {},
            system_id: params.system_id,
          },
        },
      }),
      reducer: () => {},
    },
    deleteError: statusHandlers.delete.error as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    deleteNotify: (
      state: ControllerState,
      action: PayloadAction<Controller[ControllerMeta.PK]>
    ) => {
      const index = state.items.findIndex(
        (item: Controller) => item.system_id === action.payload
      );
      state.items.splice(index, 1);
      state.selected = state.selected.filter(
        (controllerId: Controller[ControllerMeta.PK]) =>
          controllerId !== action.payload
      );
      // Clean up the statuses for model.
      delete state.statuses[action.payload];
    },
    deleteStart: statusHandlers.delete.start as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    deleteSuccess: statusHandlers.delete.success as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    fetchSuccess: (
      state: ControllerState,
      action: PayloadAction<Controller[]>
    ) => {
      action.payload.forEach((newItem: Controller) => {
        // Add items that don't already exist in the store. Existing items
        // are probably ControllerDetails so this would overwrite them with the
        // simple controller. Existing items will be kept up to date via the
        // notify (sync) messages.
        const existing = state.items.find(
          (draftItem: Controller) => draftItem.id === newItem.id
        );
        if (!existing) {
          state.items.push(newItem);
          // Set up the statuses for this controller.
          state.statuses[newItem.system_id] = DEFAULT_STATUSES;
        }
      });
      state.loading = false;
      state.loaded = true;
    },
    ...generateGetReducers<ControllerState, Controller, ControllerMeta.PK>({
      modelName: ControllerMeta.MODEL,
      primaryKey: ControllerMeta.PK,
      defaultStatuses: DEFAULT_STATUSES,
      setErrors,
    }),
    getSummaryXml: {
      prepare: (params: GetSummaryXmlParams) => ({
        meta: {
          model: ControllerMeta.MODEL,
          method: "get_summary_xml",
          // This request needs to store the results in the file context.
          fileContextKey: params.fileId,
          useFileContext: true,
        },
        payload: {
          params: {
            system_id: params.systemId,
          },
        },
      }),
      reducer: () => {},
    },
    getSummaryXmlError: statusHandlers.getSummaryXml.error as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    getSummaryXmlStart: statusHandlers.getSummaryXml.start as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    getSummaryXmlSuccess: statusHandlers.getSummaryXml.success as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    getSummaryYaml: {
      prepare: (params: GetSummaryYamlParams) => ({
        meta: {
          model: ControllerMeta.MODEL,
          method: "get_summary_yaml",
          // This request needs to store the results in the file context.
          fileContextKey: params.fileId,
          useFileContext: true,
        },
        payload: {
          params: {
            system_id: params.systemId,
          },
        },
      }),
      reducer: () => {},
    },
    getSummaryYamlError: statusHandlers.getSummaryYaml.error as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    getSummaryYamlStart: statusHandlers.getSummaryYaml.start as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    getSummaryYamlSuccess: statusHandlers.getSummaryYaml.success as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    importImages: {
      prepare: (params: BaseNodeActionParams) => ({
        meta: {
          model: ControllerMeta.MODEL,
          method: "action",
        },
        payload: {
          params: {
            action: NodeActions.IMPORT_IMAGES,
            extra: {},
            system_id: params.system_id,
          },
        },
      }),
      reducer: () => {},
    },
    importImagesError: statusHandlers.importImages.error as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    importImagesStart: statusHandlers.importImages.start as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    importImagesSuccess: statusHandlers.importImages.success as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    off: {
      prepare: (params: BaseNodeActionParams) => ({
        meta: {
          model: ControllerMeta.MODEL,
          method: "action",
        },
        payload: {
          params: {
            action: NodeActions.OFF,
            extra: {},
            system_id: params.system_id,
          },
        },
      }),
      reducer: () => {},
    },
    offError: statusHandlers.off.error as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    offStart: statusHandlers.off.start as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    offSuccess: statusHandlers.off.success as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    on: {
      prepare: (params: BaseNodeActionParams) => ({
        meta: {
          model: ControllerMeta.MODEL,
          method: "action",
        },
        payload: {
          params: {
            action: NodeActions.ON,
            extra: {},
            system_id: params.system_id,
          },
        },
      }),
      reducer: () => {},
    },
    onError: statusHandlers.on.error as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    onStart: statusHandlers.on.start as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    onSuccess: statusHandlers.on.success as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    overrideFailedTesting: {
      prepare: (params: BaseNodeActionParams) => ({
        meta: {
          model: ControllerMeta.MODEL,
          method: "action",
        },
        payload: {
          params: {
            action: NodeActions.OVERRIDE_FAILED_TESTING,
            extra: {},
            system_id: params.system_id,
          },
        },
      }),
      reducer: () => {},
    },
    overrideFailedTestingError: statusHandlers.overrideFailedTesting
      .error as CaseReducer<ControllerState, PayloadAction<unknown>>,
    overrideFailedTestingStart: statusHandlers.overrideFailedTesting
      .start as CaseReducer<ControllerState, PayloadAction<unknown>>,
    overrideFailedTestingSuccess: statusHandlers.overrideFailedTesting
      .success as CaseReducer<ControllerState, PayloadAction<unknown>>,
    pollCheckImages: {
      prepare: (ids: Controller[ControllerMeta.PK][], pollId: string) => ({
        meta: {
          model: ControllerMeta.MODEL,
          method: "check_images",
          poll: true,
          // There may be multiple check_images request being polled for
          // different controllers so manage this polling request with an ID.
          pollId,
          pollInterval: 30000,
        },
        payload: {
          params: ids.map((id) => ({ [ControllerMeta.PK]: id })),
        },
      }),
      reducer: () => {},
    },
    pollCheckImagesError: {
      prepare: (item: CheckImagesItem[], error: ControllerState["errors"]) => ({
        meta: {
          item,
        },
        payload: error,
      }),
      reducer: (
        state: ControllerState,
        action: PayloadAction<
          ControllerState["errors"],
          string,
          GenericItemMeta<CheckImagesItem[]>
        >
      ) => {
        state = setErrors(state, action, "checkImages");
        action.meta.item.forEach(({ system_id }) => {
          if (system_id in state.statuses) {
            state.statuses[system_id].checkingImages = false;
          }
        });
      },
    },
    pollCheckImagesStart: {
      prepare: (item: CheckImagesItem[]) => ({
        meta: {
          item,
        },
        payload: null,
      }),
      reducer: (
        state: ControllerState,
        action: PayloadAction<null, string, GenericItemMeta<CheckImagesItem[]>>
      ) => {
        action.meta.item.forEach(({ system_id }) => {
          if (system_id in state.statuses) {
            state.statuses[system_id].checkingImages = true;
          }
        });
      },
    },
    pollCheckImagesStop: {
      prepare: (pollId: string) => ({
        meta: {
          model: ControllerMeta.MODEL,
          method: "check_images",
          pollId,
          pollStop: true,
        },
        payload: null,
      }),
      reducer: () => {},
    },
    pollCheckImagesSuccess: {
      prepare: (item: CheckImagesItem[], payload: ImageSyncStatuses) => ({
        meta: {
          item,
        },
        payload,
      }),
      reducer: (
        state: ControllerState,
        action: PayloadAction<
          ImageSyncStatuses,
          string,
          GenericItemMeta<CheckImagesItem[]>
        >
      ) => {
        // Insert or overwrite statuses for the controllers in this request.
        state.imageSyncStatuses = {
          ...state.imageSyncStatuses,
          ...action.payload,
        };
        action.meta.item.forEach(({ system_id }) => {
          if (system_id in state.statuses) {
            state.statuses[system_id].checkingImages = false;
          }
        });
      },
    },
    setActive: {
      prepare: (system_id: Controller[ControllerMeta.PK] | null) => ({
        meta: {
          model: ControllerMeta.MODEL,
          method: "set_active",
        },
        payload: {
          // Server unsets active item if primary key (system_id) is not sent.
          params: system_id ? { system_id } : null,
        },
      }),
      reducer: () => {},
    },
    setActiveError: (
      state: ControllerState,
      action: PayloadAction<ControllerState["errors"]>
    ) => {
      state.active = null;
      state.errors = action.payload;
      state = setErrors(state, action, "setActive");
    },
    setActiveSuccess: (
      state: ControllerState,
      action: PayloadAction<Controller | null>
    ) => {
      state.active = action.payload?.system_id || null;
    },
    setSelected: (
      state: ControllerState,
      action: PayloadAction<Controller[ControllerMeta.PK][]>
    ) => {
      state.selected = action.payload;
    },
    setZone: {
      prepare: (params: SetZoneParams) => ({
        meta: {
          model: ControllerMeta.MODEL,
          method: "action",
        },
        payload: {
          params: {
            action: NodeActions.SET_ZONE,
            extra: {
              zone_id: params.zone_id,
            },
            system_id: params.system_id,
          },
        },
      }),
      reducer: () => {},
    },
    setZoneError: statusHandlers.setZone.error as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    setZoneStart: statusHandlers.setZone.start as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    setZoneSuccess: statusHandlers.setZone.success as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    test: {
      prepare: (params: TestParams) => ({
        meta: {
          model: ControllerMeta.MODEL,
          method: "action",
        },
        payload: {
          params: {
            action: NodeActions.TEST,
            extra: {
              enable_ssh: params.enable_ssh,
              script_input: params.script_input,
              testing_scripts: params.testing_scripts,
            },
            system_id: params.system_id,
          },
        },
      }),
      reducer: () => {},
    },
    testError: statusHandlers.test.error as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    testStart: statusHandlers.test.start as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
    testSuccess: statusHandlers.test.success as CaseReducer<
      ControllerState,
      PayloadAction<unknown>
    >,
  },
});

export const { actions } = controllerSlice;

export default controllerSlice.reducer;
