import { extend } from "cooky-cutter";
import { Factory } from "fishery";
import { adjectives, uniqueNamesGenerator } from "unique-names-generator";

import { timestampedModel } from "./model";

import type { SpaceResponse } from "@/app/apiclient";
import type { Space } from "@/app/store/space/types";
import type { TimestampedModel } from "@/app/store/types/model";

export const space = extend<TimestampedModel, Space>(timestampedModel, {
  description: "a space",
  name: (i: number) => `test space ${i}`,
  subnet_ids: () => [],
  vlan_ids: () => [],
});

export const spaceV3 = Factory.define<SpaceResponse>(({ sequence }) => {
  const name = uniqueNamesGenerator({
    dictionaries: [adjectives],
    style: "lowerCase",
    seed: sequence,
    length: 1,
  });

  return {
    id: sequence,
    name,
    description: "a space",
    subnets: {
      href: "",
    },
    vlans: {
      href: "",
    },
    kind: "Space",
  };
});
