/**
 * Selector for all usable architectures.
 */

import { generateGeneralSelector } from "./utils";

const architectures = generateGeneralSelector<"architectures">("architectures");

export default architectures;
