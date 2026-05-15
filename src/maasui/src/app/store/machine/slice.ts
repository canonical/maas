import type { CaseReducer, PayloadAction } from "@reduxjs/toolkit";
import { createSlice } from "@reduxjs/toolkit";

import { ACTIONS, DEFAULT_STATUSES } from "./constants";
import type {
  ApplyStorageLayoutParams,
  BaseMachineActionParams,
  CloneParams,
  CommissionParams,
  CreateBcacheParams,
  CreateBondParams,
  CreateBridgeParams,
  CreateCacheSetParams,
  CreateLogicalVolumeParams,
  CreateParams,
  CreatePartitionParams,
  CreatePhysicalParams,
  CreateRaidParams,
  CreateVlanParams,
  CreateVmfsDatastoreParams,
  CreateVolumeGroupParams,
  DeleteCacheSetParams,
  DeleteDiskParams,
  DeleteFilesystemParams,
  DeleteInterfaceParams,
  DeletePartitionParams,
  DeleteVolumeGroupParams,
  DeployParams,
  FetchParams,
  FetchResponse,
  FetchResponseGroup,
  FilterGroupOption,
  FilterGroupOptionType,
  FilterGroupResponse,
  GetSummaryXmlParams,
  GetSummaryYamlParams,
  LinkSubnetParams,
  Machine,
  MachineDetails,
  MachineState,
  MachineStateCount,
  MachineStateDetailsItem,
  MachineStateList,
  MarkBrokenParams,
  MountSpecialParams,
  ReleaseParams,
  SetBootDiskParams,
  SetPoolParams,
  SetZoneParams,
  TagParams,
  TestParams,
  UnlinkSubnetParams,
  UnmountSpecialParams,
  UntagParams,
  UpdateDiskParams,
  UpdateFilesystemParams,
  UpdateParams,
  UpdateVmfsDatastoreParams,
  FetchFilters,
  SelectedMachines,
  FilterGroupKey,
} from "./types";
import { MachineMeta, FilterGroupType } from "./types";
import type { OverrideFailedTesting } from "./types/actions";
import type { MachineActionStatus, MachineStateListGroup } from "./types/base";
import { createMachineListGroup, isMachineDetails } from "./utils";

import { ACTION_STATUS } from "@/app/base/constants";
import type { ScriptResult } from "@/app/store/scriptresult/types";
import type { UpdateInterfaceParams } from "@/app/store/types/node";
import { NodeActions } from "@/app/store/types/node";
import { generateStatusHandlers, updateErrors } from "@/app/store/utils";
import type {
  StatusHandlers,
  GenericItemMeta,
  GenericMeta,
} from "@/app/store/utils/slice";
import {
  generateCommonReducers,
  genericInitialState,
} from "@/app/store/utils/slice";
import { preparePayloadParams, kebabToCamelCase } from "@/app/utils";

export const DEFAULT_MACHINE_QUERY_STATE = {
  params: null,
  fetchedAt: null,
  refetchedAt: null,
  refetching: false,
} as const;

export const DEFAULT_LIST_STATE = {
  count: null,
  cur_page: null,
  errors: null,
  groups: null,
  loaded: false,
  loading: true,
  stale: false,
  num_pages: null,
  ...DEFAULT_MACHINE_QUERY_STATE,
} as const;

export const DEFAULT_COUNT_STATE = {
  loading: false,
  loaded: false,
  stale: false,
  count: null,
  errors: null,
  ...DEFAULT_MACHINE_QUERY_STATE,
} as const;

const isArrayOfOptionsType = <T extends FilterGroupOptionType>(
  options: FilterGroupOption[],
  typeString: string
): options is FilterGroupOption<T>[] =>
  options.every(({ key }) => typeof key === typeString);

/**
 * Wrap the updateError call so that the call is made with the correct generics.
 */
const setErrors = (
  state: MachineState,
  action: PayloadAction<MachineState["errors"]> | null,
  event: string | null
): MachineState =>
  updateErrors<MachineState, MachineMeta.PK>(
    state,
    action,
    event,
    MachineMeta.PK
  );

const statusHandlers = generateStatusHandlers<
  MachineState,
  Machine,
  MachineMeta.PK,
  MachineActionStatus
>(
  MachineMeta.PK,
  ACTIONS.map((action) => {
    const handler: StatusHandlers<
      MachineState,
      Machine,
      MachineActionStatus | null
    > = {
      status: kebabToCamelCase(action.name),
      start: (state, action) => {
        if (action.meta.callId) {
          if (action.meta.callId in state.actions) {
            state.actions[action.meta.callId].status = ACTION_STATUS.loading;
          } else {
            state.actions[action.meta.callId] = {
              status: ACTION_STATUS.loading,
              errors: null,
              successCount: 0,
              failedSystemIds: [],
              failureDetails: {},
            };
          }
        }
      },
      success: (state, action) => {
        if (action.meta.callId) {
          const actionsItem = state.actions[action.meta.callId];

          if (action.meta.callId in state.actions && action.payload) {
            actionsItem.status = ACTION_STATUS.success;
            if (action.payload && "success_count" in action.payload) {
              actionsItem.successCount = action.payload.success_count;
            }
            if (
              "failed_system_ids" in action.payload &&
              action.payload.failed_system_ids?.length > 0
            ) {
              actionsItem.status = ACTION_STATUS.error;
              actionsItem.failedSystemIds = [
                ...action.payload.failed_system_ids,
              ] as Machine[MachineMeta.PK][];
              actionsItem.failureDetails = {
                ...action.payload.failure_details,
              };
            }
          } else if (actionsItem) {
            actionsItem.status = ACTION_STATUS.error;
          }
        }
      },
      error: (state, action) => {
        if (action.meta.callId) {
          if (action.meta.callId in state.actions) {
            const actionsItem = state.actions[action.meta.callId];
            actionsItem.status = "error";
            actionsItem.errors = action.payload;
          }
        }
      },
      method: "action",
      statusKey: action.status,
    };
    return handler;
  }),
  setErrors
);

const generateActionParams = <P extends BaseMachineActionParams>(
  action: NodeActions
) => ({
  prepare: (params: P, callId?: string) => {
    let actionParams: BaseMachineActionParams & {
      action: NodeActions;
      extra: Omit<P, "filter" | "system_id"> | Omit<P, "system_id">;
    };
    if ("filter" in params) {
      // Separate the filter and 'extra' params.
      const { filter, system_id, ...extra } = params;
      actionParams = {
        action,
        extra,
        system_id,
        filter,
      };
    } else {
      // Separate the id and 'extra' params.
      const { system_id, ...extra } = params;
      actionParams = {
        action,
        extra,
        system_id,
      };
    }
    return {
      meta: {
        model: MachineMeta.MODEL,
        method: "action",
        ...(callId ? { callId } : {}),
      },
      payload: {
        params: actionParams,
      },
    } as const;
  },
  reducer: () => {},
});

const invalidateQueries = (state: MachineState) => {
  Object.keys(state.lists).forEach((callId) => {
    state.lists[callId].stale = true;
  });
  Object.keys(state.counts).forEach((callId) => {
    state.counts[callId].stale = true;
  });
};

const machineSlice = createSlice({
  name: MachineMeta.MODEL,
  initialState: {
    ...genericInitialState,
    actions: {},
    active: null,
    counts: {},
    details: {},
    eventErrors: [],
    filters: [],
    filtersLoaded: false,
    filtersLoading: false,
    lists: {},
    selected: null,
    statuses: {},
  } as MachineState,
  reducers: {
    ...generateCommonReducers<
      MachineState,
      MachineMeta.PK,
      CreateParams,
      UpdateParams
    >({
      modelName: MachineMeta.MODEL,
      primaryKey: MachineMeta.PK,
      setErrors,
    }),
    [NodeActions.ABORT]: generateActionParams<BaseMachineActionParams>(
      NodeActions.ABORT
    ),
    [`${NodeActions.ABORT}Error`]: statusHandlers.abort.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.ABORT}Start`]: statusHandlers.abort.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.ABORT}Success`]: statusHandlers.abort
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    [NodeActions.ACQUIRE]: generateActionParams<BaseMachineActionParams>(
      NodeActions.ACQUIRE
    ),
    [`${NodeActions.ACQUIRE}Error`]: statusHandlers.acquire
      .error as CaseReducer<MachineState, PayloadAction<unknown>>,
    [`${NodeActions.ACQUIRE}Start`]: statusHandlers.acquire
      .start as CaseReducer<MachineState, PayloadAction<unknown>>,
    [`${NodeActions.ACQUIRE}Success`]: statusHandlers.acquire
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    addChassis: {
      prepare: (params: Record<string, string>) => ({
        payload: {
          params,
        },
      }),
      reducer: () => {},
    },
    addChassisError: (
      state: MachineState,
      action: PayloadAction<MachineState["errors"]>
    ) => {
      state.errors = action.payload;
      state = setErrors(state, action, "addChassis");
      state.loading = false;
      state.saving = false;
    },
    addChassisStart: (state: MachineState) => {
      state.saved = false;
      state.saving = true;
    },
    addChassisSuccess: (state: MachineState) => {
      state.errors = null;
      state.saved = true;
      state.saving = false;
    },
    applyStorageLayout: {
      prepare: (params: ApplyStorageLayoutParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "apply_storage_layout",
        },
        payload: {
          params: {
            storage_layout: params.storageLayout,
            system_id: params.systemId,
          },
        },
      }),
      reducer: () => {},
    },
    applyStorageLayoutError: statusHandlers.applyStorageLayout
      .error as CaseReducer<MachineState, PayloadAction<unknown>>,
    applyStorageLayoutStart: statusHandlers.applyStorageLayout
      .start as CaseReducer<MachineState, PayloadAction<unknown>>,
    applyStorageLayoutSuccess: statusHandlers.applyStorageLayout
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    checkPower: {
      prepare: (system_id: Machine[MachineMeta.PK]) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "check_power",
        },
        payload: {
          params: {
            system_id,
          },
        },
      }),
      reducer: () => {},
    },
    checkPowerError: statusHandlers.checkPower.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    checkPowerStart: statusHandlers.checkPower.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    checkPowerSuccess: statusHandlers.checkPower.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [NodeActions.CLONE]: generateActionParams<CloneParams>(NodeActions.CLONE),
    cloneError: statusHandlers.clone.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    cloneStart: statusHandlers.clone.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    cloneSuccess: statusHandlers.clone.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [NodeActions.COMMISSION]: generateActionParams<CommissionParams>(
      NodeActions.COMMISSION
    ),
    [`${NodeActions.COMMISSION}Error`]: statusHandlers.commission
      .error as CaseReducer<MachineState, PayloadAction<unknown>>,
    [`${NodeActions.COMMISSION}Start`]: statusHandlers.commission
      .start as CaseReducer<MachineState, PayloadAction<unknown>>,
    [`${NodeActions.COMMISSION}Success`]: statusHandlers.commission
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    createBcache: {
      prepare: (params: CreateBcacheParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "create_bcache",
        },
        payload: {
          params: preparePayloadParams(params, {
            cacheMode: "cache_mode",
            cacheSetId: "cache_set",
            systemId: MachineMeta.PK,
            blockId: "block_id",
            mountOptions: "mount_options",
            mountPoint: "mount_point",
            partitionId: "partition_id",
          }),
        },
      }),
      reducer: () => {},
    },
    count: {
      prepare: (callId: string, filters?: FetchFilters | null) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "count",
          callId,
        },
        payload: filters
          ? {
              params: { filter: filters },
            }
          : null,
      }),
      reducer: () => {},
    },
    countError: {
      prepare: (callId: string, errors: MachineStateCount["errors"]) => ({
        meta: {
          callId,
        },
        payload: errors,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<MachineStateCount["errors"], string, GenericMeta>
      ) => {
        if (action.meta.callId) {
          state.counts[action.meta.callId] = {
            ...(action.meta.callId in state.counts
              ? state.counts[action.meta.callId]
              : DEFAULT_COUNT_STATE),
            errors: action.payload,
            loading: false,
          };
        }
        state = setErrors(state, action, "count");
      },
    },
    countStart: {
      prepare: (callId: string) => ({
        meta: {
          callId,
        },
        payload: null,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<null, string, GenericMeta>
      ) => {
        if (action.meta.callId) {
          if (action.meta.callId in state.counts) {
            // refetching
            state.counts[action.meta.callId].refetching = true;
            state.counts[action.meta.callId].refetchedAt = Date.now();
          } else {
            // initial fetch
            state.counts[action.meta.callId] = {
              ...DEFAULT_COUNT_STATE,
              loading: true,
              params: action.meta.item || null,
              fetchedAt: Date.now(),
            };
          }
        }
      },
    },
    countSuccess: {
      prepare: (callId: string, count: { count: number }) => ({
        meta: {
          callId,
        },
        payload: count,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<{ count: number }, string, GenericMeta>
      ) => {
        // Only update state if this call exists in the store. This check is required
        // because the call may have been cleaned up in the time the API takes
        // to respond.
        if (action.meta.callId && action.meta.callId in state.counts) {
          state.counts[action.meta.callId] = {
            ...(action.meta.callId in state.counts
              ? state.counts[action.meta.callId]
              : DEFAULT_COUNT_STATE),
            stale: false,
            count: action.payload.count,
            loading: false,
            loaded: true,
          };
        }
      },
    },
    createBcacheError: statusHandlers.createBcache.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createBcacheStart: statusHandlers.createBcache.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createBcacheSuccess: statusHandlers.createBcache.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createBond: {
      prepare: (params: CreateBondParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "create_bond",
        },
        payload: {
          params: preparePayloadParams(params),
        },
      }),
      reducer: () => {},
    },
    createBondError: statusHandlers.createBond.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createBondStart: statusHandlers.createBond.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createBondSuccess: statusHandlers.createBond.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createBridge: {
      prepare: (params: CreateBridgeParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "create_bridge",
        },
        payload: {
          params: preparePayloadParams(params),
        },
      }),
      reducer: () => {},
    },
    createBridgeError: statusHandlers.createBridge.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createBridgeStart: statusHandlers.createBridge.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createBridgeSuccess: statusHandlers.createBridge.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createCacheSet: {
      prepare: (params: CreateCacheSetParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "create_cache_set",
        },
        payload: {
          params: preparePayloadParams(params, {
            blockId: "block_id",
            partitionId: "partition_id",
            systemId: MachineMeta.PK,
          }),
        },
      }),
      reducer: () => {},
    },
    createCacheSetError: statusHandlers.createCacheSet.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createCacheSetStart: statusHandlers.createCacheSet.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createCacheSetSuccess: statusHandlers.createCacheSet.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createLogicalVolume: {
      prepare: (params: CreateLogicalVolumeParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "create_logical_volume",
        },
        payload: {
          params: preparePayloadParams(params, {
            mountOptions: "mount_options",
            mountPoint: "mount_point",
            systemId: MachineMeta.PK,
            volumeGroupId: "volume_group_id",
          }),
        },
      }),
      reducer: () => {},
    },
    createLogicalVolumeError: statusHandlers.createLogicalVolume
      .error as CaseReducer<MachineState, PayloadAction<unknown>>,
    createLogicalVolumeStart: statusHandlers.createLogicalVolume
      .start as CaseReducer<MachineState, PayloadAction<unknown>>,
    createLogicalVolumeSuccess: statusHandlers.createLogicalVolume
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    createPartition: {
      prepare: (params: CreatePartitionParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "create_partition",
        },
        payload: {
          params: {
            block_id: params.blockId,
            fstype: params.fstype,
            mount_options: params.mountOptions,
            mount_point: params.mountPoint,
            partition_size: params.partitionSize,
            system_id: params.systemId,
          },
        },
      }),
      reducer: () => {},
    },
    createPartitionError: statusHandlers.createPartition.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createPartitionStart: statusHandlers.createPartition.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createPartitionSuccess: statusHandlers.createPartition
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    createPhysical: {
      prepare: (params: CreatePhysicalParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "create_physical",
        },
        payload: {
          params: preparePayloadParams(params),
        },
      }),
      reducer: () => {},
    },
    createPhysicalError: statusHandlers.createPhysical.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createPhysicalStart: statusHandlers.createPhysical.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createPhysicalSuccess: statusHandlers.createPhysical.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createRaid: {
      prepare: (params: CreateRaidParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "create_raid",
        },
        payload: {
          params: preparePayloadParams(params, {
            blockDeviceIds: "block_devices",
            mountOptions: "mount_options",
            mountPoint: "mount_point",
            partitionIds: "partitions",
            spareBlockDeviceIds: "spare_devices",
            sparePartitionIds: "spare_partitions",
            systemId: MachineMeta.PK,
          }),
        },
      }),
      reducer: () => {},
    },
    createRaidError: statusHandlers.createRaid.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createRaidStart: statusHandlers.createRaid.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createRaidSuccess: statusHandlers.createRaid.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createVlan: {
      prepare: (params: CreateVlanParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "create_vlan",
        },
        payload: {
          params: preparePayloadParams(params),
        },
      }),
      reducer: () => {},
    },
    createVlanError: statusHandlers.createVlan.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createVlanStart: statusHandlers.createVlan.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createVlanSuccess: statusHandlers.createVlan.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    createVmfsDatastore: {
      prepare: (params: CreateVmfsDatastoreParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "create_vmfs_datastore",
        },
        payload: {
          params: preparePayloadParams(params, {
            blockDeviceIds: "block_devices",
            partitionIds: "partitions",
            systemId: MachineMeta.PK,
          }),
        },
      }),
      reducer: () => {},
    },
    createVmfsDatastoreError: statusHandlers.createVmfsDatastore
      .error as CaseReducer<MachineState, PayloadAction<unknown>>,
    createVmfsDatastoreStart: statusHandlers.createVmfsDatastore
      .start as CaseReducer<MachineState, PayloadAction<unknown>>,
    createVmfsDatastoreSuccess: statusHandlers.createVmfsDatastore
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    createVolumeGroup: {
      prepare: (params: CreateVolumeGroupParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "create_volume_group",
        },
        payload: {
          params: preparePayloadParams(params, {
            blockDeviceIds: "block_devices",
            partitionIds: "partitions",
            systemId: MachineMeta.PK,
          }),
        },
      }),
      reducer: () => {},
    },
    createVolumeGroupError: statusHandlers.createVolumeGroup
      .error as CaseReducer<MachineState, PayloadAction<unknown>>,
    createVolumeGroupStart: statusHandlers.createVolumeGroup
      .start as CaseReducer<MachineState, PayloadAction<unknown>>,
    createVolumeGroupSuccess: statusHandlers.createVolumeGroup
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    [NodeActions.DELETE]: generateActionParams<BaseMachineActionParams>(
      NodeActions.DELETE
    ),
    [`${NodeActions.DELETE}Error`]: statusHandlers.delete.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.DELETE}Start`]: statusHandlers.delete.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.DELETE}Success`]: statusHandlers.delete
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    [`${NodeActions.DELETE}Notify`]: (state: MachineState, action) => {
      const index = state.items.findIndex(
        (item: Machine) => item.system_id === action.payload
      );
      state.items.splice(index, 1);
      if (
        state.selected &&
        "items" in state.selected &&
        state.selected.items &&
        state.selected.items.length > 0
      ) {
        state.selected.items = state.selected.items.filter(
          (machineId: Machine[MachineMeta.PK]) => machineId !== action.payload
        );
      }
      // Remove deleted machine from all lists
      Object.values(state.lists).forEach((list) => {
        list.groups?.forEach((group) => {
          const index = group.items.indexOf(action.payload);
          if (index !== -1) {
            group.items.splice(index, 1);
            // update the count
            if (group.count && group.count > 0) {
              group.count = group.count - 1;
            }
            if (list.count && list.count > 0) {
              list.count = list.count - 1;
            }
            // Exit the loop early if the item has been found and removed
            return;
          }
        });
        // remove unknown empty groups
        if (list.groups) {
          list.groups = list.groups?.filter((group) => group.items.length > 0);
        }
      });

      // we do not know if the deleted machine is in the the requested count
      // mark all machine count queries as stale and in need of re-fetch
      Object.keys(state.counts).forEach((callId) => {
        state.counts[callId].stale = true;
      });

      // Clean up the statuses for model.
      delete state.statuses[action.payload];
    },
    deleteCacheSet: {
      prepare: (params: DeleteCacheSetParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "delete_cache_set",
        },
        payload: {
          params: {
            cache_set_id: params.cacheSetId,
            system_id: params.systemId,
          },
        },
      }),
      reducer: () => {},
    },
    deleteCacheSetError: statusHandlers.deleteCacheSet.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    deleteCacheSetStart: statusHandlers.deleteCacheSet.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    deleteCacheSetSuccess: statusHandlers.deleteCacheSet.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    deleteDisk: {
      prepare: (params: DeleteDiskParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "delete_disk",
        },
        payload: {
          params: {
            block_id: params.blockId,
            system_id: params.systemId,
          },
        },
      }),
      reducer: () => {},
    },
    deleteDiskError: statusHandlers.deleteDisk.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    deleteDiskStart: statusHandlers.deleteDisk.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    deleteDiskSuccess: statusHandlers.deleteDisk.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    deleteFilesystem: {
      prepare: (params: DeleteFilesystemParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "delete_filesystem",
        },
        payload: {
          params: preparePayloadParams(params, {
            blockDeviceId: "blockdevice_id",
            filesystemId: "filesystem_id",
            partitionId: "partition_id",
            systemId: MachineMeta.PK,
          }),
        },
      }),
      reducer: () => {},
    },
    deleteFilesystemError: statusHandlers.deleteFilesystem.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    deleteFilesystemStart: statusHandlers.deleteFilesystem.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    deleteFilesystemSuccess: statusHandlers.deleteFilesystem
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    deleteInterface: {
      prepare: (params: DeleteInterfaceParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "delete_interface",
        },
        payload: {
          params: {
            interface_id: params.interfaceId,
            system_id: params.systemId,
          },
        },
      }),
      reducer: () => {},
    },
    deleteInterfaceError: statusHandlers.deleteInterface.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    deleteInterfaceStart: statusHandlers.deleteInterface.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    deleteInterfaceSuccess: statusHandlers.deleteInterface
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    deletePartition: {
      prepare: (params: DeletePartitionParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "delete_partition",
        },
        payload: {
          params: {
            partition_id: params.partitionId,
            system_id: params.systemId,
          },
        },
      }),
      reducer: () => {},
    },
    deletePartitionError: statusHandlers.deletePartition.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    deletePartitionStart: statusHandlers.deletePartition.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    deletePartitionSuccess: statusHandlers.deletePartition
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    deleteVolumeGroup: {
      prepare: (params: DeleteVolumeGroupParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "delete_volume_group",
        },
        payload: {
          params: {
            system_id: params.systemId,
            volume_group_id: params.volumeGroupId,
          },
        },
      }),
      reducer: () => {},
    },
    deleteVolumeGroupError: statusHandlers.deleteVolumeGroup
      .error as CaseReducer<MachineState, PayloadAction<unknown>>,
    deleteVolumeGroupStart: statusHandlers.deleteVolumeGroup
      .start as CaseReducer<MachineState, PayloadAction<unknown>>,
    deleteVolumeGroupSuccess: statusHandlers.deleteVolumeGroup
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    [NodeActions.DEPLOY]: generateActionParams<DeployParams>(
      NodeActions.DEPLOY
    ),
    [`${NodeActions.DEPLOY}Error`]: statusHandlers.deploy.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.DEPLOY}Start`]: statusHandlers.deploy.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.DEPLOY}Success`]: statusHandlers.deploy
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    exitRescueMode: generateActionParams<BaseMachineActionParams>(
      NodeActions.EXIT_RESCUE_MODE
    ),
    exitRescueModeError: statusHandlers.exitRescueMode.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    exitRescueModeStart: statusHandlers.exitRescueMode.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    exitRescueModeSuccess: statusHandlers.exitRescueMode.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    fetch: {
      prepare: (callId: string, params?: FetchParams | null) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "list",
          nocache: true,
          callId,
        },
        payload: params
          ? {
              params,
            }
          : null,
      }),
      reducer: () => {},
    },
    fetchError: {
      prepare: (callId: string, errors: MachineStateList["errors"]) => ({
        meta: {
          callId,
        },
        payload: errors,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<MachineStateList["errors"], string, GenericMeta>
      ) => {
        if (action.meta.callId) {
          if (action.meta.callId in state.lists) {
            state.lists[action.meta.callId].errors = action.payload;
            state.lists[action.meta.callId].loading = false;
          }
        }
        state = setErrors(state, action, "fetch");
      },
    },
    fetchStart: {
      prepare: (callId: string) => ({
        meta: {
          callId,
        },
        payload: null,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<null, string, GenericMeta>
      ) => {
        if (action.meta.callId) {
          if (!state.lists[action.meta.callId]) {
            // initial fetch
            state.lists[action.meta.callId] = {
              ...DEFAULT_LIST_STATE,
              loading: true,
              params: action.meta.item || null,
              fetchedAt: Date.now(),
            };
          } else {
            // refetching
            state.lists[action.meta.callId].refetching = true;
            state.lists[action.meta.callId].params = action.meta.item || null;
            state.lists[action.meta.callId].refetchedAt = Date.now();
          }
        }
      },
    },
    fetchSuccess: {
      prepare: (callId: string, payload: FetchResponse) => ({
        meta: {
          callId,
        },
        payload,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<FetchResponse, string, GenericMeta>
      ) => {
        const { callId } = action.meta;
        // Only update state if this call exists in the store. This check is required
        // because the call may have been cleaned up in the time the API takes
        // to respond.
        if (callId && callId in state.lists) {
          action.payload.groups.forEach((group: FetchResponseGroup) => {
            group.items.forEach((newItem: Machine) => {
              // Add items that don't already exist in the store. Existing items
              // are probably MachineDetails so this would overwrite them with the
              // simple machine. Existing items will be kept up to date via the
              // notify (sync) messages.
              const existingIndex = state.items.findIndex(
                (draftItem: Machine) => draftItem.id === newItem.id
              );
              if (!state.items[existingIndex]) {
                state.items.push(newItem);
                // Set up the statuses for this machine.
                state.statuses[newItem.system_id] = DEFAULT_STATUSES;
                // update existing item if not of machine details type
              } else if (
                state.items[existingIndex] &&
                !isMachineDetails(state.items[existingIndex])
              ) {
                state.items[existingIndex] = newItem;
              }
            });
          });
          const { payload } = action;
          state.lists[callId].stale = false;
          state.lists[callId].count = payload.count;
          state.lists[callId].cur_page = payload.cur_page;
          state.lists[callId].groups = payload.groups.map((group) => ({
            ...group,
            items: group.items.map(({ system_id }) => system_id),
          }));
          state.lists[callId].loaded = true;
          state.lists[callId].loading = false;
          state.lists[callId].num_pages = payload.num_pages;
        }
      },
    },
    // marks all queries as stale which will trigger a re-fetch
    invalidateQueries,
    filterGroups: {
      prepare: () => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "filter_groups",
        },
        payload: null,
      }),
      reducer: () => {},
    },
    filterGroupsError: (
      state: MachineState,
      action: PayloadAction<MachineState["errors"]>
    ) => {
      state.errors = action.payload;
      state = setErrors(state, action, "filterGroups");
      state.filtersLoading = false;
    },
    filterGroupsStart: (state: MachineState) => {
      state.filtersLoading = true;
    },
    filterGroupsSuccess: (
      state: MachineState,
      action: PayloadAction<FilterGroupResponse[]>
    ) => {
      state.filters = action.payload.map((response) => ({
        ...response,
        errors: null,
        loaded: false,
        loading: false,
        options: null,
      }));
      state.filtersLoading = false;
      state.filtersLoaded = true;
    },
    filterOptions: {
      prepare: (groupKey: FilterGroupKey) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "filter_options",
        },
        payload: {
          params: {
            group_key: groupKey,
          },
        },
      }),
      reducer: () => {},
    },
    filterOptionsError: {
      prepare: (
        groupKey: FilterGroupKey,
        errors: MachineStateDetailsItem["errors"]
      ) => ({
        meta: {
          item: {
            group_key: groupKey,
          },
        },
        payload: errors,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<
          MachineStateDetailsItem["errors"],
          string,
          GenericItemMeta<{ group_key: FilterGroupKey }>
        >
      ) => {
        // Find the group for the requested key.
        const filterGroup = state.filters.find(
          ({ key }) => key === action.meta.item.group_key
        );
        if (filterGroup) {
          filterGroup.errors = action.payload;
          filterGroup.loading = false;
        }
        state = setErrors(state, action, "filterOptions");
      },
    },
    filterOptionsStart: {
      prepare: (groupKey: FilterGroupKey) => ({
        meta: {
          item: {
            group_key: groupKey,
          },
        },
        payload: null,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<
          null,
          string,
          GenericItemMeta<{ group_key: FilterGroupKey }>
        >
      ) => {
        // Find the group for the requested key.
        const filterGroup = state.filters.find(
          ({ key }) => key === action.meta.item.group_key
        );
        if (filterGroup) {
          filterGroup.loading = true;
        }
      },
    },
    filterOptionsSuccess: {
      prepare: (groupKey: FilterGroupKey, payload: FilterGroupOption[]) => ({
        meta: {
          item: {
            group_key: groupKey,
          },
        },
        payload,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<
          FilterGroupOption[],
          string,
          GenericItemMeta<{ group_key: FilterGroupKey }>
        >
      ) => {
        // Find the group for the requested key.
        const filterGroup = state.filters.find(
          ({ key }) => key === action.meta.item.group_key
        );
        if (filterGroup) {
          // Remove unknown blank options.
          const options = action.payload.filter(
            ({ key, label }) => key || label
          );
          // Narrow the type of the response to match the expected options
          // and instert the options inside the filter group.
          if (
            filterGroup.type === FilterGroupType.Bool &&
            isArrayOfOptionsType<boolean>(options, "boolean")
          ) {
            filterGroup.options = options;
          } else if (
            [
              FilterGroupType.Float,
              FilterGroupType.FloatList,
              FilterGroupType.Int,
              FilterGroupType.IntList,
            ].includes(filterGroup.type) &&
            isArrayOfOptionsType<number>(options, "number")
          ) {
            filterGroup.options = options;
          } else if (
            [
              FilterGroupType.String,
              FilterGroupType.StringList,
              FilterGroupType.Dict,
            ].includes(filterGroup.type) &&
            isArrayOfOptionsType<string>(options, "string")
          ) {
            filterGroup.options = options;
          }
          filterGroup.loading = false;
          filterGroup.loaded = true;
        }
      },
    },
    cleanupRequest: {
      prepare: (callId: string) =>
        ({
          meta: {
            callId,
            model: MachineMeta.MODEL,
            unsubscribe: true,
          },
          payload: null,
        }) as const,
      reducer: () => {},
    },
    get: {
      prepare: (machineID: Machine[MachineMeta.PK], callId: string) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "get",
          callId,
        },
        payload: {
          params: { system_id: machineID },
        },
      }),
      reducer: () => {},
    },
    getError: {
      prepare: (
        item: { system_id: Machine[MachineMeta.PK] },
        callId: string,
        errors: MachineStateDetailsItem["errors"]
      ) => ({
        meta: {
          item,
          callId,
        },
        payload: errors,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<
          MachineStateDetailsItem["errors"],
          string,
          GenericItemMeta<{ system_id: Machine[MachineMeta.PK] }>
        >
      ) => {
        if (action.meta.callId && action.meta.callId in state.details) {
          state.details[action.meta.callId].errors = action.payload;
          state.details[action.meta.callId].loading = false;
        }
        state = setErrors(state, action, "get");
      },
    },
    getStart: {
      prepare: (
        item: { system_id: Machine[MachineMeta.PK] },
        callId: string
      ) => ({
        meta: {
          item,
          callId,
        },
        payload: null,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<
          null,
          string,
          GenericItemMeta<{ system_id: Machine[MachineMeta.PK] }>
        >
      ) => {
        if (action.meta.callId) {
          if (action.meta.callId in state.details) {
            state.details[action.meta.callId].loading = true;
          } else {
            state.details[action.meta.callId] = {
              errors: null,
              loaded: false,
              loading: true,
              system_id: action.meta.item.system_id,
            };
          }
        }
      },
    },
    getSuccess: {
      prepare: (
        item: { system_id: Machine[MachineMeta.PK] },
        callId: string,
        machine: MachineDetails
      ) => ({
        meta: {
          item,
          callId,
        },
        payload: machine,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<
          MachineDetails,
          string,
          GenericItemMeta<{ system_id: Machine[MachineMeta.PK] }>
        >
      ) => {
        const { callId } = action.meta;
        // Only update state if this call exists in the store. This check is required
        // because the call may have been cleaned up in the time the API takes
        // to respond.
        if (callId && callId in state.details) {
          const machine = action.payload;
          // If the item already exists, update it, otherwise
          // add it to the store.
          const i = state.items.findIndex(
            (draftItem: Machine) => draftItem.system_id === machine.system_id
          );
          if (i !== -1) {
            state.items[i] = machine;
          } else {
            state.items.push(machine);
            // Set up the statuses for this machine.
            state.statuses[machine.system_id] = DEFAULT_STATUSES;
          }
          state.details[callId].loading = false;
          state.details[callId].loaded = true;
        }
      },
    },
    getSummaryXml: {
      prepare: (params: GetSummaryXmlParams) => ({
        meta: {
          model: MachineMeta.MODEL,
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
      MachineState,
      PayloadAction<unknown>
    >,
    getSummaryXmlStart: statusHandlers.getSummaryXml.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    getSummaryXmlSuccess: statusHandlers.getSummaryXml.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    getSummaryYaml: {
      prepare: (params: GetSummaryYamlParams) => ({
        meta: {
          model: MachineMeta.MODEL,
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
      MachineState,
      PayloadAction<unknown>
    >,
    getSummaryYamlStart: statusHandlers.getSummaryYaml.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    getSummaryYamlSuccess: statusHandlers.getSummaryYaml.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    linkSubnet: {
      prepare: (params: LinkSubnetParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "link_subnet",
        },
        payload: {
          params: preparePayloadParams(params),
        },
      }),
      reducer: () => {},
    },
    linkSubnetError: statusHandlers.linkSubnet.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    linkSubnetStart: statusHandlers.linkSubnet.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    linkSubnetSuccess: statusHandlers.linkSubnet.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [NodeActions.LOCK]: generateActionParams<BaseMachineActionParams>(
      NodeActions.LOCK
    ),
    [`${NodeActions.LOCK}Error`]: statusHandlers.lock.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.LOCK}Start`]: statusHandlers.lock.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.LOCK}Success`]: statusHandlers.lock.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    markBroken: generateActionParams<MarkBrokenParams>(NodeActions.MARK_BROKEN),
    markBrokenError: statusHandlers.markBroken.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    markBrokenStart: statusHandlers.markBroken.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    markBrokenSuccess: statusHandlers.markBroken.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    markFixed: generateActionParams<BaseMachineActionParams>(
      NodeActions.MARK_FIXED
    ),
    markFixedError: statusHandlers.markFixed.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    markFixedStart: statusHandlers.markFixed.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    markFixedSuccess: statusHandlers.markFixed.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    mountSpecial: {
      prepare: (params: MountSpecialParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "mount_special",
        },
        payload: {
          params: {
            fstype: params.fstype,
            mount_options: params.mountOptions,
            mount_point: params.mountPoint,
            system_id: params.systemId,
          },
        },
      }),
      reducer: () => {},
    },
    mountSpecialError: statusHandlers.mountSpecial.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    mountSpecialStart: statusHandlers.mountSpecial.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    mountSpecialSuccess: statusHandlers.mountSpecial.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [NodeActions.OFF]: generateActionParams<BaseMachineActionParams>(
      NodeActions.OFF
    ),
    [`${NodeActions.OFF}Error`]: statusHandlers.off.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.OFF}Start`]: statusHandlers.off.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.OFF}Success`]: statusHandlers.off.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [NodeActions.ON]: generateActionParams<BaseMachineActionParams>(
      NodeActions.ON
    ),
    [`${NodeActions.ON}Error`]: statusHandlers.on.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.ON}Start`]: statusHandlers.on.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.ON}Success`]: statusHandlers.on.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    overrideFailedTesting: generateActionParams<OverrideFailedTesting>(
      NodeActions.OVERRIDE_FAILED_TESTING
    ),
    overrideFailedTestingError: statusHandlers.overrideFailedTesting
      .error as CaseReducer<MachineState, PayloadAction<unknown>>,
    overrideFailedTestingStart: statusHandlers.overrideFailedTesting
      .start as CaseReducer<MachineState, PayloadAction<unknown>>,
    overrideFailedTestingSuccess: statusHandlers.overrideFailedTesting
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    [NodeActions.RELEASE]: generateActionParams<ReleaseParams>(
      NodeActions.RELEASE
    ),
    [`${NodeActions.RELEASE}Error`]: statusHandlers.release
      .error as CaseReducer<MachineState, PayloadAction<unknown>>,
    [`${NodeActions.RELEASE}Start`]: statusHandlers.release
      .start as CaseReducer<MachineState, PayloadAction<unknown>>,
    [`${NodeActions.RELEASE}Success`]: statusHandlers.release
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    // TODO: Add actual functionality here once the backend is ready https://warthogs.atlassian.net/browse/MAASENG-4185
    powerCycle: {
      prepare: () => ({ payload: null }),
      reducer: () => {},
    },
    removeRequest: {
      prepare: (callId: string) =>
        ({
          meta: {
            callId,
          },
          payload: null,
        }) as const,
      reducer: (
        state: MachineState,
        action: PayloadAction<null, string, GenericMeta>
      ) => {
        const { callId } = action.meta;
        if (callId) {
          if (callId in state.details) {
            delete state.details[callId];
          } else if (callId in state.actions) {
            delete state.actions[callId];
          }
        }
      },
    },
    rescueMode: generateActionParams<BaseMachineActionParams>(
      NodeActions.RESCUE_MODE
    ),
    rescueModeError: statusHandlers.rescueMode.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    rescueModeStart: statusHandlers.rescueMode.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    rescueModeSuccess: statusHandlers.rescueMode.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    setActive: {
      prepare: (system_id: Machine[MachineMeta.PK] | null) => ({
        meta: {
          model: MachineMeta.MODEL,
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
      state: MachineState,
      action: PayloadAction<MachineState["errors"]>
    ) => {
      state.active = null;
      state.errors = action.payload;
      state = setErrors(state, action, "setActive");
    },
    setActiveSuccess: (
      state: MachineState,
      action: PayloadAction<Machine | null>
    ) => {
      state.active = action.payload?.system_id || null;
    },
    setBootDisk: {
      prepare: (params: SetBootDiskParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "set_boot_disk",
        },
        payload: {
          params: {
            block_id: params.blockId,
            system_id: params.systemId,
          },
        },
      }),
      reducer: () => {},
    },
    setBootDiskError: statusHandlers.setBootDisk.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    setBootDiskStart: statusHandlers.setBootDisk.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    setBootDiskSuccess: statusHandlers.setBootDisk.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    setPool: generateActionParams<SetPoolParams>(NodeActions.SET_POOL),
    setPoolError: statusHandlers.setPool.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    setPoolStart: statusHandlers.setPool.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    setPoolSuccess: statusHandlers.setPool.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    setSelected: {
      prepare: (selected: SelectedMachines | null) => ({
        payload: selected,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<SelectedMachines | null>
      ) => {
        state.selected = action.payload;
      },
    },
    setZone: generateActionParams<SetZoneParams>(NodeActions.SET_ZONE),
    setZoneError: statusHandlers.setZone.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    setZoneStart: statusHandlers.setZone.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    setZoneSuccess: statusHandlers.setZone.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    softOff: {
      prepare: (params: BaseMachineActionParams) => {
        let actionParams;
        if ("filter" in params) {
          const { filter, system_id, ...extra } = params;
          actionParams = {
            action: NodeActions.OFF,
            filter,
            system_id,
            extra: { ...extra, stop_mode: "soft" },
          };
        } else {
          const { system_id, ...extra } = params;
          actionParams = {
            action: NodeActions.OFF,
            extra: { ...extra, stop_mode: "soft" },
            system_id,
          };
        }
        return {
          meta: {
            model: MachineMeta.MODEL,
            method: "action",
          },
          payload: {
            params: actionParams,
          },
        };
      },
      reducer: () => {},
    },
    softOffError: statusHandlers.softOff.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    softOffStart: statusHandlers.softOff.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    softOffSuccess: statusHandlers.softOff.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    suppressScriptResults: {
      prepare: (
        machineID: Machine[MachineMeta.PK],
        scripts: ScriptResult[]
      ) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "set_script_result_suppressed",
        },
        payload: {
          params: {
            system_id: machineID,
            script_result_ids: scripts.map((script) => script.id),
          },
        },
      }),
      reducer: () => {},
    },
    [NodeActions.TAG]: generateActionParams<TagParams>(NodeActions.TAG),
    [`${NodeActions.TAG}Error`]: statusHandlers.tag.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.TAG}Start`]: statusHandlers.tag.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.TAG}Success`]: statusHandlers.tag.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [NodeActions.TEST]: generateActionParams<TestParams>(NodeActions.TEST),
    [`${NodeActions.TEST}Error`]: statusHandlers.test.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.TEST}Start`]: statusHandlers.test.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.TEST}Success`]: statusHandlers.test.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [NodeActions.UNLOCK]: generateActionParams<BaseMachineActionParams>(
      NodeActions.UNLOCK
    ),
    [`${NodeActions.UNLOCK}Error`]: statusHandlers.unlock.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.UNLOCK}Start`]: statusHandlers.unlock.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    [`${NodeActions.UNLOCK}Success`]: statusHandlers.unlock
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    unlinkSubnet: {
      prepare: (params: UnlinkSubnetParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "unlink_subnet",
        },
        payload: {
          params: {
            interface_id: params.interfaceId,
            link_id: params.linkId,
            system_id: params.systemId,
          },
        },
      }),
      reducer: () => {},
    },
    unlinkSubnetError: statusHandlers.unlinkSubnet.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    unlinkSubnetStart: statusHandlers.unlinkSubnet.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    unlinkSubnetSuccess: statusHandlers.unlinkSubnet.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    unmountSpecial: {
      prepare: (params: UnmountSpecialParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "unmount_special",
        },
        payload: {
          params: {
            mount_point: params.mountPoint,
            system_id: params.systemId,
          },
        },
      }),
      reducer: () => {},
    },
    unmountSpecialError: statusHandlers.unmountSpecial.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    unmountSpecialStart: statusHandlers.unmountSpecial.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    unmountSpecialSuccess: statusHandlers.unmountSpecial.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    unsuppressScriptResults: {
      prepare: (
        machineID: Machine[MachineMeta.PK],
        scripts: ScriptResult[]
      ) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "set_script_result_unsuppressed",
        },
        payload: {
          params: {
            system_id: machineID,
            script_result_ids: scripts.map((script) => script.id),
          },
        },
      }),
      reducer: () => {},
    },
    unsubscribe: {
      prepare: (ids: Machine[MachineMeta.PK][]) =>
        ({
          meta: {
            model: MachineMeta.MODEL,
            method: "unsubscribe",
          },
          payload: {
            params: { system_ids: ids },
          },
        }) as const,
      reducer: () => {},
    },
    unsubscribeError: (
      state: MachineState,
      action: PayloadAction<MachineState["errors"]>
    ) => {
      state.errors = action.payload;
      state = setErrors(state, action, "unsubscribe");
    },
    unsubscribeStart: {
      prepare: (ids: Machine[MachineMeta.PK][]) => ({
        meta: {
          item: { system_ids: ids },
        },
        payload: null,
      }),
      reducer: (
        state: MachineState,
        action: PayloadAction<
          null,
          string,
          GenericItemMeta<{ system_ids: Machine[MachineMeta.PK][] }>
        >
      ) => {
        action.meta.item.system_ids.forEach((id) => {
          if (state.statuses[id]) {
            state.statuses[id].unsubscribing = true;
          }
        });
      },
    },
    unsubscribeSuccess: (
      state: MachineState,
      action: PayloadAction<Machine[MachineMeta.PK][]>
    ) => {
      action.payload.forEach((id) => {
        // Clean up the statuses for model.
        state.statuses[id] = { ...DEFAULT_STATUSES };
      });
    },
    [NodeActions.UNTAG]: generateActionParams<UntagParams>(NodeActions.UNTAG),
    untagError: statusHandlers.untag.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    untagStart: statusHandlers.untag.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    untagSuccess: statusHandlers.untag.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    updateDisk: {
      prepare: (params: UpdateDiskParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "update_disk",
        },
        payload: {
          params: preparePayloadParams(params, {
            blockId: "block_id",
            mountOptions: "mount_options",
            mountPoint: "mount_point",
            systemId: MachineMeta.PK,
          }),
        },
      }),
      reducer: () => {},
    },
    updateDiskError: statusHandlers.updateDisk.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    updateDiskStart: statusHandlers.updateDisk.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    updateDiskSuccess: statusHandlers.updateDisk.success as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    updateFilesystem: {
      prepare: (params: UpdateFilesystemParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "update_filesystem",
        },
        payload: {
          params: preparePayloadParams(params, {
            blockId: "block_id",
            mountOptions: "mount_options",
            mountPoint: "mount_point",
            partitionId: "partition_id",
            systemId: MachineMeta.PK,
          }),
        },
      }),
      reducer: () => {},
    },
    updateFilesystemError: statusHandlers.updateFilesystem.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    updateFilesystemStart: statusHandlers.updateFilesystem.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    updateFilesystemSuccess: statusHandlers.updateFilesystem
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    updateInterface: {
      prepare: (
        // This update endpoint is used for updating all interface types so
        // must allow all possible parameters.
        params: UpdateInterfaceParams
      ) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "update_interface",
        },
        payload: {
          params: preparePayloadParams(params),
        },
      }),
      reducer: () => {},
    },
    updateInterfaceError: statusHandlers.updateInterface.error as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    updateInterfaceStart: statusHandlers.updateInterface.start as CaseReducer<
      MachineState,
      PayloadAction<unknown>
    >,
    updateInterfaceSuccess: statusHandlers.updateInterface
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
    updateNotify: (
      state: MachineState,
      action: PayloadAction<MachineState["items"][0]>
    ) => {
      generateCommonReducers<
        MachineState,
        MachineMeta.PK,
        CreateParams,
        UpdateParams
      >({
        modelName: MachineMeta.MODEL,
        primaryKey: MachineMeta.PK,
        setErrors,
      }).updateNotify(state, action);
      // infer the new grouping value for each machine list
      // based on machine details sent as notification payload
      Object.keys(state.lists).forEach((callId: string) => {
        const list: MachineStateList = state.lists[callId];
        let groups: MachineStateListGroup[] = list.groups ?? [];
        const groupBy = list.params?.group_key ?? "";
        const machine = action.payload;

        // if groupBy is empty string, then we don't need to do unknownthing
        if (groupBy === "") {
          return;
        }

        const currentMachineListGroup = groups?.find((group) =>
          group.items.some((systemId) => systemId === action.payload.system_id)
        );
        // get the right value from action.payload based on the groupKey
        const newMachineListGroup = createMachineListGroup({
          groupBy,
          machine,
        });

        if (!currentMachineListGroup || !newMachineListGroup) {
          return;
        }

        // update the groups if machine grouping changed
        if (currentMachineListGroup.value !== newMachineListGroup.value) {
          // remove machine from the current group
          groups = groups.map((group) => {
            if (group.value === currentMachineListGroup.value) {
              return {
                ...group,
                items: group.items.filter(
                  (item) => item !== action.payload.system_id
                ),
                // decrement count by 1 if count is known,
                // otherwise set to null indicating it needs to be fetched
                count: group.count ? group.count - 1 : null,
              };
            }
            return group;
          });

          // add machine to the new group
          const newGroupExists = groups.find(
            (group) => group.value === newMachineListGroup.value
          );
          if (newGroupExists) {
            groups = groups.map((group) => {
              if (group.value === newMachineListGroup.value) {
                return {
                  ...group,
                  items: [...group.items, action.payload.system_id],
                  // increment count by 1 if count is known,
                  // otherwise set to null indicating it needs to be fetched
                  count: group.count ? group.count + 1 : null,
                };
              }
              return group;
            });
          } else {
            // if the group does not exist create it
            groups.push({
              name: newMachineListGroup.name,
              value: newMachineListGroup.value,
              items: [action.payload.system_id],
              // set count to null indicating it's unknown and needs to be fetched
              count: null,
              collapsed: false,
            });
          }

          // remove unknown empty groups
          groups = groups.filter((group) => group.items.length > 0);

          // update the list
          list.groups = groups;
        }
      });

      // machine update can affect counts of filtered machine lists
      // - mark all filtered machine counts as stale indicating they need to be fetched
      Object.keys(state.counts).forEach((callId) => {
        if (state.counts[callId].params !== null) {
          state.counts[callId].stale = true;
        }
      });
    },
    updateVmfsDatastore: {
      prepare: (params: UpdateVmfsDatastoreParams) => ({
        meta: {
          model: MachineMeta.MODEL,
          method: "update_vmfs_datastore",
        },
        payload: {
          params: preparePayloadParams(params, {
            blockDeviceIds: "add_block_devices",
            partitionIds: "add_partitions",
            systemId: MachineMeta.PK,
            vmfsDatastoreId: "vmfs_datastore_id",
          }),
        },
      }),
      reducer: () => {},
    },
    updateVmfsDatastoreError: statusHandlers.updateVmfsDatastore
      .error as CaseReducer<MachineState, PayloadAction<unknown>>,
    updateVmfsDatastoreStart: statusHandlers.updateVmfsDatastore
      .start as CaseReducer<MachineState, PayloadAction<unknown>>,
    updateVmfsDatastoreSuccess: statusHandlers.updateVmfsDatastore
      .success as CaseReducer<MachineState, PayloadAction<unknown>>,
  },
  extraReducers: (builder) => {
    // Invalidate all machine queries when the websocket disconnects
    // This ensures we have the latest data when the connection resumes
    // and necessary model subscriptions (update notifications) are reactivated.
    builder.addCase("status/websocketDisconnected", invalidateQueries);
  },
});

export const { actions } = machineSlice;

export default machineSlice.reducer;
