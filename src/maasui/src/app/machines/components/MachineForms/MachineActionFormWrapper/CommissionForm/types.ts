import type { Script } from "@/app/store/script/types";
import type { ScriptInputParam } from "@/app/store/types/node";

export type CommissionFormValues = {
  enableSSH: boolean;
  skipBMCConfig: boolean;
  skipNetworking: boolean;
  skipStorage: boolean;
  updateFirmware: boolean;
  configureHBA: boolean;
  commissioningScripts: Script[];
  testingScripts: Script[];
  scriptInputs: ScriptInputParam;
};

export type FormattedScript = Script & {
  displayName: string;
};
