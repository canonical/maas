import { Factory } from "fishery";
import {
  adjectives,
  animals,
  uniqueNamesGenerator,
} from "unique-names-generator";

import type { RackWithSummaryResponse } from "@/app/apiclient";

export const rackFactory = Factory.define<RackWithSummaryResponse>(
  ({ sequence }) => {
    const name = uniqueNamesGenerator({
      dictionaries: [adjectives, animals],
      separator: "_",
      style: "lowerCase",
      seed: sequence,
    });
    return {
      id: sequence,
      name,
      registered_agents_system_ids: [`controller-${sequence}`],
    };
  }
);
