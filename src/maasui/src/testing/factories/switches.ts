import { Factory } from "fishery";
import {
  adjectives,
  animals,
  uniqueNamesGenerator,
} from "unique-names-generator";

import type { SwitchItem } from "@/app/switches/types";

export const switchFactory = Factory.define<SwitchItem>(({ sequence }) => {
  const name = uniqueNamesGenerator({
    dictionaries: [adjectives, animals],
    separator: "-",
    style: "lowerCase",
    seed: sequence,
  });

  return {
    id: sequence,
    name,
    mac_address: `00:00:00:00:00:${sequence}`,
    status: "Ready",
    ztp_enabled: sequence % 2 !== 0,
  };
});
