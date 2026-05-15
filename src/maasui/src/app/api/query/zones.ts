import type { UseQueryResult } from "@tanstack/react-query";
import { useQueryClient, useMutation } from "@tanstack/react-query";

import { useWebsocketAwareQuery } from "@/app/api/query/base";
import {
  mutationOptionsWithHeaders,
  queryOptionsWithHeaders,
} from "@/app/api/utils";
import type {
  CreateZoneData,
  CreateZoneErrors,
  CreateZoneResponses,
  DeleteZoneData,
  DeleteZoneErrors,
  DeleteZoneResponses,
  GetZoneData,
  GetZoneErrors,
  GetZoneResponses,
  ListZonesData,
  ListZonesErrors,
  ListZonesResponses,
  ListZonesWithStatisticsData,
  ListZonesWithStatisticsErrors,
  ListZonesWithStatisticsResponses,
  Options,
  UpdateZoneData,
  UpdateZoneErrors,
  UpdateZoneResponses,
  ZoneWithStatisticsResponse,
} from "@/app/apiclient";
import {
  deleteZone,
  updateZone,
  createZone,
  getZone,
  listZonesWithStatistics,
  listZones,
} from "@/app/apiclient";
import {
  getZoneQueryKey,
  listZonesQueryKey,
  listZonesWithStatisticsQueryKey,
} from "@/app/apiclient/@tanstack/react-query.gen";

type UseZonesResult = {
  data:
    | {
        items: {
          statistics: ZoneWithStatisticsResponse | undefined;
          id: number;
          name: string;
          description: string;
        }[];
        total: number;
      }
    | undefined;
  isPending: UseQueryResult["isPending"];
  isSuccess: UseQueryResult["isSuccess"];
  isError: UseQueryResult["isError"];
};

export const useZones = (options?: Options<ListZonesData>): UseZonesResult => {
  const zones = useWebsocketAwareQuery(
    queryOptionsWithHeaders<ListZonesResponses, ListZonesErrors, ListZonesData>(
      options,
      listZones,
      listZonesQueryKey(options)
    )
  );
  const zoneIds = zones.data?.items.map((zone) => zone.id) ?? [];
  const statistics = useZonesStatistics({
    query: { id: zoneIds },
  });

  return {
    ...zones,
    data: zones.data
      ? {
          ...zones.data,
          items: zones.data.items.map((zone) => ({
            ...zone,
            statistics: statistics.data?.items.find(
              (stat) => stat.id === zone.id
            ),
          })),
        }
      : undefined,
  };
};

export const useZonesStatistics = (
  options?: Options<ListZonesWithStatisticsData>,
  enabled?: boolean
) => {
  return useWebsocketAwareQuery({
    ...queryOptionsWithHeaders<
      ListZonesWithStatisticsResponses,
      ListZonesWithStatisticsErrors,
      ListZonesWithStatisticsData
    >(
      options,
      listZonesWithStatistics,
      listZonesWithStatisticsQueryKey(options)
    ),
    enabled,
  });
};

export const useZoneCount = (options?: Options<ListZonesData>) => {
  return useWebsocketAwareQuery({
    ...queryOptionsWithHeaders<
      ListZonesResponses,
      ListZonesErrors,
      ListZonesData
    >(options, listZones, listZonesQueryKey(options)),
    select: (data) => data?.total ?? 0,
  });
};

export const useGetZone = (options: Options<GetZoneData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<GetZoneResponses, GetZoneErrors, GetZoneData>(
      options,
      getZone,
      getZoneQueryKey(options)
    )
  );
};

export const useCreateZone = (mutationOptions?: Options<CreateZoneData>) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      CreateZoneResponses,
      CreateZoneErrors,
      CreateZoneData
    >(mutationOptions, createZone),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listZonesQueryKey(),
      });
    },
  });
};

export const useUpdateZone = (mutationOptions?: Options<UpdateZoneData>) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      UpdateZoneResponses,
      UpdateZoneErrors,
      UpdateZoneData
    >(mutationOptions, updateZone),
    onSuccess: async () => {
      return queryClient.invalidateQueries({
        queryKey: listZonesQueryKey(),
      });
    },
  });
};

export const useDeleteZone = (mutationOptions?: Options<DeleteZoneData>) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      DeleteZoneResponses,
      DeleteZoneErrors,
      DeleteZoneData
    >(mutationOptions, deleteZone),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listZonesQueryKey(),
      });
    },
  });
};
