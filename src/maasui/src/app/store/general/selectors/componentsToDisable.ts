/**
 * Selector for components that can be disabled for default Ubuntu archives.
 */

import { generateGeneralSelector } from "./utils";

const componentsToDisable = generateGeneralSelector<"componentsToDisable">(
  "componentsToDisable"
);

export default componentsToDisable;
