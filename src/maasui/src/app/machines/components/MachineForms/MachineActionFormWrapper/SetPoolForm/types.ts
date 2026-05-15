import type { ResourcePoolResponse } from "@/app/apiclient";

export type SetPoolFormValues = {
  description: ResourcePoolResponse["description"];
  name: ResourcePoolResponse["name"];
  poolSelection: "create" | "select";
};
