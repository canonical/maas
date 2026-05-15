import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useWebsocketAwareQuery } from "./base";

import {
  mutationOptionsWithHeaders,
  queryOptionsWithHeaders,
} from "@/app/api/utils";
import type {
  CreateResourcePoolData,
  CreateResourcePoolErrors,
  CreateResourcePoolResponses,
  DeleteResourcePoolData,
  DeleteResourcePoolErrors,
  DeleteResourcePoolResponses,
  GetResourcePoolData,
  GetResourcePoolErrors,
  GetResourcePoolResponses,
  ListResourcePoolsStatisticsData,
  ListResourcePoolsStatisticsErrors,
  ListResourcePoolsStatisticsResponses,
  Options,
  UpdateResourcePoolData,
  UpdateResourcePoolErrors,
  UpdateResourcePoolResponses,
} from "@/app/apiclient";
import {
  createResourcePool,
  deleteResourcePool,
  updateResourcePool,
  getResourcePool,
  listResourcePoolsStatistics,
} from "@/app/apiclient";
import {
  getResourcePoolQueryKey,
  listResourcePoolsStatisticsQueryKey,
} from "@/app/apiclient/@tanstack/react-query.gen";

export const usePools = (
  options?: Options<ListResourcePoolsStatisticsData>
) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      ListResourcePoolsStatisticsResponses,
      ListResourcePoolsStatisticsErrors,
      ListResourcePoolsStatisticsData
    >(
      options,
      listResourcePoolsStatistics,
      listResourcePoolsStatisticsQueryKey(options)
    )
  );
};

export const usePoolCount = (
  options?: Options<ListResourcePoolsStatisticsData>
) => {
  return useWebsocketAwareQuery({
    ...queryOptionsWithHeaders<
      ListResourcePoolsStatisticsResponses,
      ListResourcePoolsStatisticsErrors,
      ListResourcePoolsStatisticsData
    >(
      options,
      listResourcePoolsStatistics,
      listResourcePoolsStatisticsQueryKey(options)
    ),
    select: (data) => data?.total ?? 0,
  });
};

export const useGetPool = (options: Options<GetResourcePoolData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      GetResourcePoolResponses,
      GetResourcePoolErrors,
      GetResourcePoolData
    >(options, getResourcePool, getResourcePoolQueryKey(options))
  );
};

export const useCreatePool = (
  mutationOptions?: Options<CreateResourcePoolData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      CreateResourcePoolResponses,
      CreateResourcePoolErrors,
      CreateResourcePoolData
    >(mutationOptions, createResourcePool),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listResourcePoolsStatisticsQueryKey(),
      });
    },
  });
};

export const useUpdatePool = (
  mutationOptions?: Options<UpdateResourcePoolData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      UpdateResourcePoolResponses,
      UpdateResourcePoolErrors,
      UpdateResourcePoolData
    >(mutationOptions, updateResourcePool),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listResourcePoolsStatisticsQueryKey(),
      });
    },
  });
};

export const useDeletePool = (
  mutationOptions?: Options<DeleteResourcePoolData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      DeleteResourcePoolResponses,
      DeleteResourcePoolErrors,
      DeleteResourcePoolData
    >(mutationOptions, deleteResourcePool),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listResourcePoolsStatisticsQueryKey(),
      });
    },
  });
};
