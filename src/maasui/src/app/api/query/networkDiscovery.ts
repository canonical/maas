import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useWebsocketAwareQuery } from "@/app/api/query/base";
import {
  mutationOptionsWithHeaders,
  queryOptionsWithHeaders,
} from "@/app/api/utils";
import type {
  ClearAllDiscoveriesWithOptionalIpAndMacData,
  ClearAllDiscoveriesWithOptionalIpAndMacErrors,
  ClearAllDiscoveriesWithOptionalIpAndMacResponses,
  ListDiscoveriesData,
  ListDiscoveriesErrors,
  ListDiscoveriesResponses,
  Options,
} from "@/app/apiclient";
import {
  clearAllDiscoveriesWithOptionalIpAndMac,
  listDiscoveries,
} from "@/app/apiclient";
import { listDiscoveriesQueryKey } from "@/app/apiclient/@tanstack/react-query.gen";

export const useNetworkDiscoveries = (
  options?: Options<ListDiscoveriesData>
) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      ListDiscoveriesResponses,
      ListDiscoveriesErrors,
      ListDiscoveriesData
    >(options, listDiscoveries, listDiscoveriesQueryKey(options))
  );
};

export const useClearNetworkDiscoveries = (
  mutationOptions?: Options<ClearAllDiscoveriesWithOptionalIpAndMacData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      ClearAllDiscoveriesWithOptionalIpAndMacResponses,
      ClearAllDiscoveriesWithOptionalIpAndMacErrors,
      ClearAllDiscoveriesWithOptionalIpAndMacData
    >(mutationOptions, clearAllDiscoveriesWithOptionalIpAndMac),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listDiscoveriesQueryKey(),
      });
    },
  });
};
