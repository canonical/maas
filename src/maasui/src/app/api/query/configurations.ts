import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useWebsocketAwareQuery } from "./base";

import {
  mutationOptionsWithHeaders,
  queryOptionsWithHeaders,
} from "@/app/api/utils";
import type {
  GetConfigurationData,
  GetConfigurationErrors,
  GetConfigurationResponses,
  GetConfigurationsData,
  GetConfigurationsErrors,
  GetConfigurationsResponses,
  Options,
  SetConfigurationData,
  SetConfigurationErrors,
  SetConfigurationResponses,
  SetConfigurationsData,
  SetConfigurationsErrors,
  SetConfigurationsResponses,
} from "@/app/apiclient";
import {
  getConfiguration,
  getConfigurations,
  setConfiguration,
  setConfigurations,
} from "@/app/apiclient";
import {
  getConfigurationQueryKey,
  getConfigurationsQueryKey,
} from "@/app/apiclient/@tanstack/react-query.gen";

export const useConfigurations = (options?: Options<GetConfigurationsData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      GetConfigurationsResponses,
      GetConfigurationsErrors,
      GetConfigurationsData
    >(options, getConfigurations, getConfigurationsQueryKey(options))
  );
};

export const useGetConfiguration = (options: Options<GetConfigurationData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      GetConfigurationResponses,
      GetConfigurationErrors,
      GetConfigurationData
    >(options, getConfiguration, getConfigurationQueryKey(options))
  );
};

export const useSetConfiguration = (
  mutationOptions?: Options<SetConfigurationData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      SetConfigurationResponses,
      SetConfigurationErrors,
      SetConfigurationData
    >(mutationOptions, setConfiguration),
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({
        queryKey: getConfigurationsQueryKey(),
      });
      await queryClient.invalidateQueries({
        queryKey: getConfigurationQueryKey({
          path: { name: variables.path.name },
        }),
      });
    },
  });
};

export const useBulkSetConfigurations = (
  mutationOptions?: Options<SetConfigurationsData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      SetConfigurationsResponses,
      SetConfigurationsErrors,
      SetConfigurationsData
    >(mutationOptions, setConfigurations),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: getConfigurationsQueryKey(),
      });
    },
  });
};
