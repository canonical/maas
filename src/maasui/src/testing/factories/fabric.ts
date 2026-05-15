import { extend, random } from "cooky-cutter";
import { Factory } from "fishery";
import { adjectives, uniqueNamesGenerator } from "unique-names-generator";

import { timestampedModel } from "./model";

import type { FabricResponse } from "@/app/apiclient";
import type { Fabric } from "@/app/store/fabric/types";
import type { TimestampedModel } from "@/app/store/types/model";

export const fabric = extend<TimestampedModel, Fabric>(timestampedModel, {
  class_type: "10g",
  default_vlan_id: random,
  description: "a fabric",
  name: (i: number) => `test-fabric-${i}`,
  vlan_ids: () => [],
});

export const fabricV3 = Factory.define<FabricResponse>(({ sequence }) => {
  const name = uniqueNamesGenerator({
    dictionaries: [adjectives],
    style: "lowerCase",
    seed: sequence,
    length: 1,
  });

  return {
    id: sequence,
    name,
    description: "a fabric",
    class_type: "10g",
    vlans: {
      href: "",
    },
    kind: "Fabric",
  };
});
