import type { Domain } from "@/app/store/domain/types";
import { argPath } from "@/app/utils";

const urls = {
  details: argPath<{ id: Domain["id"] }>("/domain/:id"),
  index: "/domains",
} as const;

export default urls;
