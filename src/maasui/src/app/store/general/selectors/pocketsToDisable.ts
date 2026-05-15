/**
 * Selector for pockets that can be disabled.
 */

import { generateGeneralSelector } from "./utils";

const pocketsToDisable =
  generateGeneralSelector<"pocketsToDisable">("pocketsToDisable");

export default pocketsToDisable;
