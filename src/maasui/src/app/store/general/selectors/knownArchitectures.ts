/**
 * Selector for all known architectures, usable or not.
 */

import { generateGeneralSelector } from "./utils";

const knownArchitectures =
  generateGeneralSelector<"knownArchitectures">("knownArchitectures");

export default knownArchitectures;
