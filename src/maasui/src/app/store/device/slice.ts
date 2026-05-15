import type { CaseReducer, PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import { DeviceMeta } from "./types";
import type {
  CreateInterfaceParams,
  CreateParams,
  DeviceState,
  UpdateParams,
  Device,
} from "./types";
import type {
  CreatePhysicalParams,
  DeleteInterfaceParams,
  LinkSubnetParams,
  UnlinkSubnetParams,
} from "./types/actions";

import type {
  BaseNodeActionParams,
  SetZoneParams,
  UpdateInterfaceParams,
} from "@/app/store/types/node";
import { NodeActions } from "@/app/store/types/node";
import {
  generateCommonReducers,
  generateGetReducers,
  generateStatusHandlers,
  genericInitialState,
  updateErrors,
} from "@/app/store/utils/slice";
import { kebabToCamelCase, preparePayloadParams } from "@/app/utils";

export const DEFAULT_STATUSES = {
  creatingInterface: false,
  creatingPhysical: false,
  deleting: false,
  deletingInterface: false,
  linkingSubnet: false,
  unlinkingSubnet: false,
  updatingInterface: false,
  settingZone: false,
};

const setErrors = (
  state: DeviceState,
  action: PayloadAction<DeviceState["errors"]> | null,
  event: string | null
): DeviceState =>
  updateErrors<DeviceState, DeviceMeta.PK>(state, action, event, DeviceMeta.PK);

const statusHandlers = generateStatusHandlers<
  DeviceState,
  Device,
  DeviceMeta.PK
>(
  DeviceMeta.PK,
  [
    {
      status: "createInterface",
      statusKey: "creatingInterface",
    },
    {
      status: "createPhysical",
      statusKey: "creatingPhysical",
    },
    {
      status: NodeActions.DELETE,
      statusKey: "deleting",
    },
    {
      status: "deleteInterface",
      statusKey: "deletingInterface",
    },
    {
      status: "linkSubnet",
      statusKey: "linkingSubnet",
    },
    {
      status: "unlinkSubnet",
      statusKey: "unlinkingSubnet",
    },
    {
      status: kebabToCamelCase(NodeActions.SET_ZONE),
      statusKey: "settingZone",
    },
    {
      status: "updateInterface",
      statusKey: "updatingInterface",
    },
  ],
  setErrors
);

const deviceSlice = createSlice({
  name: DeviceMeta.MODEL,
  initialState: {
    ...genericInitialState,
    active: null,
    eventErrors: [],
    selected: [],
    statuses: {},
  } as DeviceState,
  reducers: {
    ...generateCommonReducers<
      DeviceState,
      DeviceMeta.PK,
      CreateParams,
      UpdateParams
    >({
      modelName: DeviceMeta.MODEL,
      primaryKey: DeviceMeta.PK,
      setErrors,
    }),
    createInterface: {
      prepare: (params: CreateInterfaceParams) => ({
        meta: {
          model: DeviceMeta.MODEL,
          method: "create_interface",
        },
        payload: {
          params: preparePayloadParams(params),
        },
      }),
      reducer: () => {},
    },
    createInterfaceError: statusHandlers.createInterface.error as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    createInterfaceStart: statusHandlers.createInterface.start as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    createInterfaceSuccess: statusHandlers.createInterface
      .success as CaseReducer<DeviceState, PayloadAction<unknown>>,
    createNotify: (state: DeviceState, action: PayloadAction<Device>) => {
      // In the event that the server erroneously attempts to create an existing device,
      // due to a race condition etc., ensure we update instead of creating duplicates.
      const existingIdx = state.items.findIndex(
        (draftItem: Device) => draftItem.system_id === action.payload.system_id
      );
      if (existingIdx !== -1) {
        state.items[existingIdx] = action.payload;
      } else {
        state.items.push(action.payload);
        state.statuses[action.payload.system_id] = DEFAULT_STATUSES;
      }
    },
    // On the backend this endpoint is an alias for createInterface.
    createPhysical: {
      prepare: (params: CreatePhysicalParams) => ({
        meta: {
          model: DeviceMeta.MODEL,
          method: "create_physical",
        },
        payload: {
          params: preparePayloadParams(params),
        },
      }),
      reducer: () => {},
    },
    createPhysicalError: statusHandlers.createPhysical.error as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    createPhysicalStart: statusHandlers.createPhysical.start as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    createPhysicalSuccess: statusHandlers.createPhysical.success as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    fetchSuccess: (state: DeviceState, action: PayloadAction<Device[]>) => {
      action.payload.forEach((newItem: Device) => {
        // Add items that don't already exist in the store. Existing items
        // are probably DeviceDetails so this would overwrite them with the
        // simple device. Existing items will be kept up to date via the
        // notify (sync) messages.
        const existing = state.items.find(
          (draftItem: Device) => draftItem.id === newItem.id
        );
        if (!existing) {
          state.items.push(newItem);
          // Set up the statuses for this device.
          state.statuses[newItem.system_id] = DEFAULT_STATUSES;
        }
      });
      state.loading = false;
      state.loaded = true;
    },
    delete: {
      prepare: (params: BaseNodeActionParams) => ({
        meta: {
          model: DeviceMeta.MODEL,
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
      DeviceState,
      PayloadAction<unknown>
    >,
    deleteNotify: (
      state: DeviceState,
      action: PayloadAction<Device[DeviceMeta.PK]>
    ) => {
      const index = state.items.findIndex(
        (item: Device) => item.system_id === action.payload
      );
      state.items.splice(index, 1);
      state.selected = state.selected.filter(
        (deviceId: Device[DeviceMeta.PK]) => deviceId !== action.payload
      );
      // Clean up the statuses for model.
      delete state.statuses[action.payload];
    },
    deleteStart: statusHandlers.delete.start as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    deleteSuccess: statusHandlers.delete.success as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    deleteInterface: {
      prepare: (params: DeleteInterfaceParams) => ({
        meta: {
          model: DeviceMeta.MODEL,
          method: "delete_interface",
        },
        payload: {
          params: preparePayloadParams(params),
        },
      }),
      reducer: () => {},
    },
    deleteInterfaceError: statusHandlers.deleteInterface.error as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    deleteInterfaceStart: statusHandlers.deleteInterface.start as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    deleteInterfaceSuccess: statusHandlers.deleteInterface
      .success as CaseReducer<DeviceState, PayloadAction<unknown>>,
    ...generateGetReducers({
      modelName: DeviceMeta.MODEL,
      primaryKey: DeviceMeta.PK,
      defaultStatuses: DEFAULT_STATUSES,
      setErrors,
    }),
    linkSubnet: {
      prepare: (params: LinkSubnetParams) => ({
        meta: {
          model: DeviceMeta.MODEL,
          method: "link_subnet",
        },
        payload: {
          params: preparePayloadParams(params),
        },
      }),
      reducer: () => {},
    },
    linkSubnetError: statusHandlers.linkSubnet.error as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    linkSubnetStart: statusHandlers.linkSubnet.start as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    linkSubnetSuccess: statusHandlers.linkSubnet.success as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    setActive: {
      prepare: (system_id: Device[DeviceMeta.PK] | null) => ({
        meta: {
          model: DeviceMeta.MODEL,
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
      state: DeviceState,
      action: PayloadAction<DeviceState["errors"]>
    ) => {
      state.active = null;
      state.errors = action.payload;
      state = setErrors(state, action, "setActive");
    },
    setActiveSuccess: (
      state: DeviceState,
      action: PayloadAction<Device | null>
    ) => {
      state.active = action.payload?.system_id || null;
    },
    setSelected: (
      state: DeviceState,
      action: PayloadAction<Device[DeviceMeta.PK][]>
    ) => {
      state.selected = action.payload;
    },
    setZone: {
      prepare: (params: SetZoneParams) => ({
        meta: {
          model: DeviceMeta.MODEL,
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
      DeviceState,
      PayloadAction<unknown>
    >,
    setZoneStart: statusHandlers.setZone.start as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    setZoneSuccess: statusHandlers.setZone.success as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    unlinkSubnet: {
      prepare: (params: UnlinkSubnetParams) => ({
        meta: {
          model: DeviceMeta.MODEL,
          method: "unlink_subnet",
        },
        payload: {
          params: preparePayloadParams(params),
        },
      }),
      reducer: () => {},
    },
    unlinkSubnetError: statusHandlers.unlinkSubnet.error as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    unlinkSubnetStart: statusHandlers.unlinkSubnet.start as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    unlinkSubnetSuccess: statusHandlers.unlinkSubnet.success as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    updateInterface: {
      prepare: (
        // This update endpoint is used for updating all interface types so
        // must allow all possible parameters.
        params: UpdateInterfaceParams
      ) => ({
        meta: {
          model: DeviceMeta.MODEL,
          method: "update_interface",
        },
        payload: {
          params: preparePayloadParams(params),
        },
      }),
      reducer: () => {},
    },
    updateInterfaceError: statusHandlers.updateInterface.error as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    updateInterfaceStart: statusHandlers.updateInterface.start as CaseReducer<
      DeviceState,
      PayloadAction<unknown>
    >,
    updateInterfaceSuccess: statusHandlers.updateInterface
      .success as CaseReducer<DeviceState, PayloadAction<unknown>>,
  },
});

export const { actions } = deviceSlice;

export default deviceSlice.reducer;
