import { generateGeneralSelector } from "./utils";

const knownBootArchitectures =
  generateGeneralSelector<"knownBootArchitectures">("knownBootArchitectures");

export default knownBootArchitectures;
