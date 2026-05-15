import { createSelector } from "reselect";

import type { RootState } from "@/app/store/root/types";
import { ServiceMeta } from "@/app/store/service/types";
import type { Service, ServiceState } from "@/app/store/service/types";
import { generateBaseSelectors } from "@/app/store/utils";

const searchFunction = (service: Service, term: string) =>
  service.name.includes(term);

const defaultSelectors = generateBaseSelectors<
  ServiceState,
  Service,
  ServiceMeta.PK
>(ServiceMeta.MODEL, ServiceMeta.PK, searchFunction);

/**
 * Get a list of services from a list of their IDs.
 * @param state - The redux state.
 * @param serviceIDs - A list of service IDs.
 * @returns A list of services.
 */
const getByIDs = createSelector(
  [
    defaultSelectors.all,
    (_state: RootState, serviceIDs: Service[ServiceMeta.PK][]) => serviceIDs,
  ],
  (services, serviceIDs) =>
    serviceIDs.reduce<Service[]>((acc, serviceID) => {
      const service = services.find((service) => service.id === serviceID);
      if (service) {
        acc.push(service);
      }
      return acc;
    }, [])
);

const selectors = {
  ...defaultSelectors,
  getByIDs,
};

export default selectors;
