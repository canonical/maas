import { QueryClient } from "@tanstack/react-query";

// Different query keys for different methods.
export const queryKeys = {
  zones: {
    list: ["zones"],
  },
} as const;

type QueryKeys = typeof queryKeys;
type QueryKeyCategories = keyof QueryKeys;
type QueryKeySubcategories<T extends QueryKeyCategories> = keyof QueryKeys[T];

// This basically exists to get us the query key as it appears in react query, i.e. a string in an array.
export type QueryKey =
  QueryKeys[QueryKeyCategories][QueryKeySubcategories<QueryKeyCategories>];

export type QueryModel = QueryKey[number];

export const defaultQueryOptions = {
  staleTime: 5 * 60 * 1000, // 5 minutes
  cacheTime: 15 * 60 * 1000, // 15 minutes
  refetchOnWindowFocus: true,
} as const;

export const realTimeQueryOptions = {
  staleTime: 0,
  cacheTime: 60 * 1000, // 1 minute
} as const;

export const createQueryClient = (): QueryClient =>
  new QueryClient({
    defaultOptions: {
      queries: defaultQueryOptions,
    },
  });
