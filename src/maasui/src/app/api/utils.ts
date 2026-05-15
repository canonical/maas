import {
  queryOptions,
  type QueryKey,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";

import type { Options } from "@/app/apiclient";
import type { RequestResult, TDataShape } from "@/app/apiclient/client";

export type WithHeaders<T> = T & { headers?: Headers };

/**
 * Creates query options that include response headers in the returned data.
 * @param options - Optional query configuration
 * @param queryFn - API client SDK function that performs the query
 * @param queryKey - React Query key for caching and invalidation
 * @returns Query options with data augmented to include headers
 */
export const queryOptionsWithHeaders = <
  TResponses,
  TErrors,
  TData extends TDataShape = TDataShape,
  TQueryKey extends QueryKey = QueryKey,
>(
  options: Options<TData> | undefined,
  queryFn: <ThrowOnError extends boolean = true>(
    options: Options<TData, ThrowOnError>
  ) => RequestResult<TResponses, TErrors, ThrowOnError>,
  queryKey: TQueryKey
): UseQueryOptions<
  WithHeaders<TResponses[keyof TResponses]>,
  TErrors[keyof TErrors],
  WithHeaders<TResponses[keyof TResponses]>,
  TQueryKey
> => {
  return queryOptions<
    WithHeaders<TResponses[keyof TResponses]>,
    TErrors[keyof TErrors],
    WithHeaders<TResponses[keyof TResponses]>,
    TQueryKey
  >({
    queryFn: async ({ queryKey, signal }) => {
      const {
        data,
        response: { headers },
      } = await queryFn({
        ...options,
        ...(queryKey[0] as object),
        signal,
        throwOnError: true,
      } as Options<TData>);
      return { ...data, headers } as WithHeaders<TResponses[keyof TResponses]>;
    },
    queryKey,
  });
};

/**
 * Creates mutation options that include response headers in the returned data.
 * @param mutationOptions - Optional mutation configuration
 * @param mutationFn - API client SDK function that performs the mutation
 * @returns Mutation options with data augmented to include headers
 */
export const mutationOptionsWithHeaders = <
  TResponses,
  TErrors,
  TData extends TDataShape = TDataShape,
>(
  mutationOptions: Options<TData> | undefined,
  mutationFn: <ThrowOnError extends boolean = true>(
    options: Options<TData, ThrowOnError>
  ) => RequestResult<TResponses, TErrors, ThrowOnError>
): UseMutationOptions<
  WithHeaders<TResponses[keyof TResponses]>,
  TErrors[keyof TErrors],
  Options<TData>
> => {
  return {
    mutationFn: async (fnOptions) => {
      const {
        data,
        response: { headers },
      } = await mutationFn({
        ...mutationOptions,
        ...fnOptions,
        throwOnError: true,
      });
      return { ...data, headers } as WithHeaders<TResponses[keyof TResponses]>;
    },
  };
};
