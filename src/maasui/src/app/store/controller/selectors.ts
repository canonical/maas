import type { Selector } from "@reduxjs/toolkit";
import { createSelector } from "@reduxjs/toolkit";

import type { Fabric, FabricMeta } from "../fabric/types";
import type { RootState } from "../root/types";
import type { Service } from "../service/types";
import { NodeType } from "../types/node";
import type { VLAN } from "../vlan/types";

import { ACTIONS } from "./slice";
import { FilterControllers } from "./utils";

import type {
  Controller,
  ControllerState,
  ControllerStatus,
  ControllerStatuses,
} from "@/app/store/controller/types";
import { ControllerMeta } from "@/app/store/controller/types";
import serviceSelectors from "@/app/store/service/selectors";
import tagSelectors from "@/app/store/tag/selectors";
import { generateBaseSelectors } from "@/app/store/utils";
import vlanSelectors from "@/app/store/vlan/selectors";

const defaultSelectors = generateBaseSelectors<
  ControllerState,
  Controller,
  ControllerMeta.PK
>(ControllerMeta.MODEL, ControllerMeta.PK);

/**
 * Get the controller state object.
 * @param state - The redux state.
 * @returns The controller state.
 */
const controllerState = (state: RootState): ControllerState =>
  state[ControllerMeta.MODEL];

/**
 * Get the controllers statuses.
 * @param state - The redux state.
 * @returns The controller statuses.
 */
const statuses = createSelector(
  [controllerState],
  (controllerState) => controllerState.statuses
);

const statusKeys = <T extends object>(statuses: T): (keyof T)[] =>
  Object.keys(statuses) as (keyof T)[];

/**
 * Returns IDs of controllers that are currently being processed.
 * @param {RootState} state - The redux state.
 * @returns {Controller["system_id"][]} List of controllers being processed.
 */
const processing = (state: RootState): Controller[ControllerMeta.PK][] =>
  Object.keys(state.controller.statuses).filter((controllerID) =>
    statusKeys(state.controller.statuses[controllerID]).some(
      (status) => state.controller.statuses[controllerID][status] === true
    )
  );

// Create a selector for each controller status.
export const statusSelectors = ACTIONS.reduce<
  Record<string, Selector<RootState, Controller[]>>
>((selectors, { status }) => {
  selectors[status] = createSelector(
    [defaultSelectors.all, statuses],
    (controllers: Controller[], statuses: ControllerStatuses) =>
      controllers.filter(({ system_id }) => statuses[system_id][status])
  );
  return selectors;
}, {});

/**
 * Get the statuses for a controller.
 * @param state - The redux state.
 * @param id - A controller's system id.
 * @returns The controller's statuses
 */
const getStatuses = createSelector(
  [statuses, (_state: RootState, id: Controller[ControllerMeta.PK]) => id],
  (allStatuses, id) => allStatuses[id]
);

/**
 * Get a status for a controller.
 * @param state - The redux state.
 * @param id - A controller's system id.
 * @returns The controller's statuses
 */
const getStatusForController = createSelector(
  [
    statuses,
    (
      _state: RootState,
      id: Controller[ControllerMeta.PK] | null,
      status: keyof ControllerStatus
    ) => ({
      id,
      status,
    }),
  ],
  (allStatuses, { id, status }) =>
    id && id in allStatuses ? allStatuses[id][status] : false
);

/**
 * Returns the controllers which are being deleted.
 * @param state - The redux state.
 * @returns Controllers being deleted.
 */
const deleting = createSelector(
  [defaultSelectors.all, statuses],
  (controllers, statuses) =>
    controllers.filter(
      (controller) => statuses[controller.system_id]?.deleting || false
    )
);

/**
 * Select the event errors for all controllers.
 * @param state - The redux state.
 * @returns The event errors.
 */
const eventErrors = createSelector(
  [controllerState],
  (controllerState) => controllerState.eventErrors
);

/**
 * Select the event errors for a controller or controllers.
 * @param ids - A controller's system ID.
 * @param event - A controller action event.
 * @returns The event errors for the controller(s).
 */
const eventErrorsForControllers = createSelector(
  [
    eventErrors,
    (
      _state: RootState,
      ids:
        | Controller[ControllerMeta.PK]
        | Controller[ControllerMeta.PK][]
        | null,
      event?: string | null
    ) => ({
      ids,
      event,
    }),
  ],
  (errors: ControllerState["eventErrors"][0][], { ids, event }) => {
    if (!errors || !ids) {
      return [];
    }
    // If a single id has been provided then turn into an array to operate over.
    const idArray = Array.isArray(ids) ? ids : [ids];
    return errors.reduce<ControllerState["eventErrors"][0][]>(
      (matches, error) => {
        let match = false;
        const matchesId = !!error.id && idArray.includes(error.id);
        // If an event has been provided as `null` then filter for errors with
        // a null event.
        if (event || event === null) {
          match = matchesId && error.event === event;
        } else {
          match = matchesId;
        }
        if (match) {
          matches.push(error);
        }
        return matches;
      },
      []
    );
  }
);

/**
 * Returns currently active controller's system_id.
 * @param state - The redux state.
 * @returns Active controller system_id.
 */
const activeID = createSelector(
  [controllerState],
  (controllerState) => controllerState.active
);

/**
 * Returns currently active controller.
 * @param state - The redux state.
 * @returns Active controller.
 */
const active = createSelector(
  [defaultSelectors.all, activeID],
  (controllers: Controller[], activeID: Controller[ControllerMeta.PK] | null) =>
    controllers.find((controller) => activeID === controller.system_id)
);

/**
 * Returns selected controller system_ids.
 * @param state - The redux state.
 * @returns Selected controller system_ids.
 */
const selectedIDs = createSelector(
  [controllerState],
  (controllerState) => controllerState.selected
);

/**
 * Returns selected controllers.
 * @param state - The redux state.
 * @returns Selected controllers.
 */
const selected = createSelector(
  [defaultSelectors.all, selectedIDs],
  (controllers: Controller[], selectedIDs: Controller[ControllerMeta.PK][]) =>
    selectedIDs.reduce<Controller[]>((selectedControllers, id) => {
      const selectedController = controllers.find(
        (controller) => id === controller.system_id
      );
      if (selectedController) {
        selectedControllers.push(selectedController);
      }
      return selectedControllers;
    }, [])
);

/**
 * Get controllers that match search terms.
 * @param state - The redux state.
 * @param terms - The search terms to match against.
 * @returns A filtered list of controllers.
 */
const search = createSelector(
  [
    defaultSelectors.all,
    tagSelectors.all,
    (
      _state: RootState,
      terms: string | null,
      selectedIDs: Controller[ControllerMeta.PK][]
    ) => ({
      terms,
      selectedIDs,
    }),
  ],
  (items: Controller[], tags, { selectedIDs, terms }) => {
    if (!terms) {
      return items;
    }
    return FilterControllers.filterItems(items, terms, selectedIDs, { tags });
  }
);

/**
 * Get the services for a controller.
 * @param state - The redux state.
 * @param terms - The search terms to match against.
 * @returns A filtered list of controllers.
 */
const servicesForController = createSelector(
  [
    defaultSelectors.all,
    serviceSelectors.all,
    (_state: RootState, systemId?: Controller[ControllerMeta.PK] | null) => ({
      systemId,
    }),
  ],
  (controllers: Controller[], services: Service[], { systemId }) => {
    if (!systemId) {
      return null;
    }
    const controller = controllers.find(
      ({ system_id }) => system_id === systemId
    );
    if (!controller) {
      return null;
    }
    return controller.service_ids.reduce<Service[]>(
      (serviceList, serviceId) => {
        const service = services.find(({ id }) => id === serviceId);
        if (service) {
          serviceList.push(service);
        }
        return serviceList;
      },
      []
    );
  }
);

/**
 * Get image sync statuses.
 * @param state - The redux state.
 * @returns The controller state.
 */
const imageSyncStatuses = createSelector(
  [controllerState],
  (controllerState) => controllerState.imageSyncStatuses
);

/**
 * Get the statuses for a controller.
 * @param state - The redux state.
 * @param id - A controller's system id.
 * @returns The controller's statuses
 */
const imageSyncStatusesForController = createSelector(
  [
    imageSyncStatuses,
    (
      _state: RootState,
      id: Controller[ControllerMeta.PK] | null | undefined
    ) => ({
      id,
    }),
  ],
  (statuses, { id }) => (id && id in statuses ? statuses[id] : null)
);

/**
 * Get controllers for a list of controller IDs.
 * @param state - The redux state.
 * @param controllerIDs - A list of controller IDs.
 * @returns A list of controllers that match the given IDs.
 */
const getByIDs = createSelector(
  [
    defaultSelectors.all,
    (_state: RootState, controllerIDs: Controller[ControllerMeta.PK][]) => ({
      controllerIDs,
    }),
  ],
  (controllers, { controllerIDs }) =>
    controllers.filter((controller) =>
      controllerIDs.some((givenID) => controller.system_id === givenID)
    )
);

/**
 * Get all controllers for a given fabric.
 * @param state - The redux state.
 * @param fabricId - A fabric id.
 * @returns A filtered list of controllers.
 */
const getByFabricId = createSelector(
  [
    vlanSelectors.all,
    defaultSelectors.all,
    (
      _state: RootState,
      fabricId: Fabric[FabricMeta.PK] | null | undefined
    ) => ({
      fabricId,
    }),
  ],
  (vlans: VLAN[], controllers: Controller[], { fabricId }) =>
    vlans
      .filter((vlan) => vlan.fabric === fabricId)
      .reduce<VLAN["rack_sids"]>(
        (rack_sids, vlan) => [...rack_sids, ...vlan.rack_sids],
        []
      )
      .reduce<Controller[]>((acc, rack_sid) => {
        const controller = controllers.find(
          (controller) => controller.system_id === rack_sid
        );
        return controller ? [...acc, controller] : acc;
      }, [])
);

/**
 * Get all region/region-and-rack controllers.
 * @param state - The redux state.
 * @returns A list of all region/region-and-rack controllers.
 */
const getRegionControllers = createSelector(
  [defaultSelectors.all],
  (controllers: Controller[]) => {
    const regionControllers = controllers.filter((controller) => {
      return (
        controller.node_type === NodeType.REGION_CONTROLLER ||
        controller.node_type === NodeType.REGION_AND_RACK_CONTROLLER
      );
    });

    return regionControllers;
  }
);

/**
 * Get controllers separated by their vault configuration status.
 * @param state - The redux state.
 * @returns Two lists of region controllers - one where none are configured with vault, the other where all are configured with vault.
 */
const getVaultConfiguredControllers = createSelector(
  [getRegionControllers],
  (controllers: Controller[]) => {
    const unconfiguredControllers = controllers.filter((controller) => {
      return (
        controller.vault_configured === false ||
        controller.vault_configured === undefined
      );
    });
    const configuredControllers = controllers.filter((controller) => {
      return controller.vault_configured === true;
    });

    return { unconfiguredControllers, configuredControllers };
  }
);

const selectors = {
  ...defaultSelectors,
  active,
  activeID,
  deleting,
  eventErrorsForControllers,
  getByIDs,
  getStatuses,
  getStatusForController,
  getVaultConfiguredControllers,
  getRegionControllers,
  imageSyncStatuses,
  imageSyncStatusesForController,
  processing,
  search,
  selected,
  selectedIDs,
  servicesForController,
  getByFabricId,
  statuses,
};

export default selectors;
