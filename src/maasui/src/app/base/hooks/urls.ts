import { useMemo } from "react";

import { useLocation, useParams } from "react-router";

import { parseNumberId } from "@/app/utils";

type RouteParams = Record<string, string>;

/**
 * Get the id param from the URL and convert to the right type.
 * @param pk - The model id key.
 * @param key - (optional) The secondary key.
 */
export function useGetURLId<P extends RouteParams, K extends keyof P>(
  pk: "system_id",
  key?: K
): string | null;
export function useGetURLId<P extends RouteParams, K extends keyof P>(
  pk: "id",
  key?: K
): number | null;
export function useGetURLId<P extends RouteParams, K extends keyof P>(
  pk: "id" | "system_id",
  key?: K
): number | string | null {
  const { [key || "id"]: id } = useParams<P>();
  if (pk === "system_id") {
    return id || null;
  }
  return parseNumberId(id);
}

export const useQuery = (): URLSearchParams => {
  const { search } = useLocation();

  return useMemo(() => new URLSearchParams(search), [search]);
};
