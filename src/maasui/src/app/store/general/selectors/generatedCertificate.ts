/**
 * Selector for generated certificate in state.
 */

import { generateGeneralSelector } from "./utils";

const generatedCertificate = generateGeneralSelector<"generatedCertificate">(
  "generatedCertificate"
);

export default generatedCertificate;
