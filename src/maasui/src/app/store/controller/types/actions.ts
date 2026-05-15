import type { Controller, ControllerDetails, ControllerStatus } from "./base";
import type { ControllerMeta } from "./enum";

import type { ZoneResponse } from "@/app/apiclient";
import type { PowerParameters } from "@/app/store/types/node";

export type Action = {
  name: string;
  status: keyof ControllerStatus;
};

export type CreateParams = {
  description?: Controller["description"];
  domain?: Controller["domain"];
  zone?: { name: ZoneResponse["name"] };
};

export type GetSummaryXmlParams = {
  systemId: Controller[ControllerMeta.PK];
  fileId: string;
};

export type GetSummaryYamlParams = {
  systemId: Controller[ControllerMeta.PK];
  fileId: string;
};

export type UpdateParams = CreateParams & {
  [ControllerMeta.PK]: Controller[ControllerMeta.PK];
  power_parameters?: PowerParameters;
  power_type?: ControllerDetails["power_type"];
  power_parameters_skip_check?: boolean;
  tags?: Controller["tags"];
};
