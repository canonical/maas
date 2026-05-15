import { generateGeneralSelector } from "./utils";

const vaultEnabled = generateGeneralSelector<"vaultEnabled">("vaultEnabled");

export default vaultEnabled;
