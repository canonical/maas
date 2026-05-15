import type { ResourcePoolResponse } from "@/app/apiclient";
import { argPath } from "@/app/utils";

const urls = {
  add: "/pools/add",
  edit: argPath<{ id: ResourcePoolResponse["id"] }>("/pools/:id/edit"),
  delete: argPath<{ id: ResourcePoolResponse["id"] }>("/pools/:id/delete"),
  index: "/pools",
};

export default urls;
