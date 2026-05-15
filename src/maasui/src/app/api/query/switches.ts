import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useWebsocketAwareQuery } from "./base";

import {
  mutationOptionsWithHeaders,
  queryOptionsWithHeaders,
} from "@/app/api/utils";
import type {
  CreateSwitchData,
  CreateSwitchErrors,
  CreateSwitchResponses,
  DeleteSwitchData,
  DeleteSwitchErrors,
  DeleteSwitchResponses,
  GetSwitchData,
  GetSwitchErrors,
  GetSwitchResponses,
  ListSwitchesData,
  ListSwitchesErrors,
  ListSwitchesResponses,
  Options,
  UpdateSwitchData,
  UpdateSwitchErrors,
  UpdateSwitchResponses,
} from "@/app/apiclient";
import {
  createSwitch,
  deleteSwitch,
  getSwitch,
  listSwitches,
  updateSwitch,
} from "@/app/apiclient";
import {
  getSwitchQueryKey,
  listSwitchesQueryKey,
} from "@/app/apiclient/@tanstack/react-query.gen";

export const useSwitches = (options?: Options<ListSwitchesData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      ListSwitchesResponses,
      ListSwitchesErrors,
      ListSwitchesData
    >(options, listSwitches, listSwitchesQueryKey(options))
  );
};

export const useGetSwitch = (options: Options<GetSwitchData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<GetSwitchResponses, GetSwitchErrors, GetSwitchData>(
      options,
      getSwitch,
      getSwitchQueryKey(options)
    )
  );
};

export const useCreateSwitch = (
  mutationOptions?: Options<CreateSwitchData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      CreateSwitchResponses,
      CreateSwitchErrors,
      CreateSwitchData
    >(mutationOptions, createSwitch),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listSwitchesQueryKey(),
      });
    },
  });
};

export const useUpdateSwitch = (
  mutationOptions?: Options<UpdateSwitchData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      UpdateSwitchResponses,
      UpdateSwitchErrors,
      UpdateSwitchData
    >(mutationOptions, updateSwitch),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listSwitchesQueryKey(),
      });
    },
  });
};

export const useDeleteSwitch = (
  mutationOptions?: Options<DeleteSwitchData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      DeleteSwitchResponses,
      DeleteSwitchErrors,
      DeleteSwitchData
    >(mutationOptions, deleteSwitch),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listSwitchesQueryKey(),
      });
    },
  });
};
