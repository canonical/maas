import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useWebsocketAwareQuery } from "./base";

import {
  mutationOptionsWithHeaders,
  queryOptionsWithHeaders,
} from "@/app/api/utils";
import type {
  CreateRackData,
  CreateRackErrors,
  CreateRackResponses,
  DeleteRacksData,
  DeleteRacksErrors,
  DeleteRacksResponses,
  GenerateRackBootstrapTokenData,
  GenerateRackBootstrapTokenErrors,
  GenerateRackBootstrapTokenResponses,
  GetRackData,
  GetRackErrors,
  GetRackResponses,
  ListRacksWithSummaryData,
  ListRacksWithSummaryErrors,
  ListRacksWithSummaryResponses,
  Options,
  UpdateRackData,
  UpdateRackErrors,
  UpdateRackResponses,
} from "@/app/apiclient";
import {
  listRacksWithSummary,
  createRack,
  deleteRacks,
  generateRackBootstrapToken,
  updateRack,
  getRack,
} from "@/app/apiclient";
import {
  getRackQueryKey,
  listRacksWithSummaryQueryKey,
} from "@/app/apiclient/@tanstack/react-query.gen";

export const useRacks = (options?: Options<ListRacksWithSummaryData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      ListRacksWithSummaryResponses,
      ListRacksWithSummaryErrors,
      ListRacksWithSummaryData
    >(options, listRacksWithSummary, listRacksWithSummaryQueryKey(options))
  );
};

export const useGetRack = (options: Options<GetRackData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<GetRackResponses, GetRackErrors, GetRackData>(
      options,
      getRack,
      getRackQueryKey(options)
    )
  );
};

export const useCreateRack = (mutationOptions?: Options<CreateRackData>) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      CreateRackResponses,
      CreateRackErrors,
      CreateRackData
    >(mutationOptions, createRack),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listRacksWithSummaryQueryKey(),
      });
    },
  });
};

export const useUpdateRack = (mutationOptions?: Options<UpdateRackData>) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      UpdateRackResponses,
      UpdateRackErrors,
      UpdateRackData
    >(mutationOptions, updateRack),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listRacksWithSummaryQueryKey(),
      });
    },
  });
};

export const useDeleteRack = (mutationOptions?: Options<DeleteRacksData>) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      DeleteRacksResponses,
      DeleteRacksErrors,
      DeleteRacksData
    >(mutationOptions, deleteRacks),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listRacksWithSummaryQueryKey(),
      });
    },
  });
};

export const useGenerateToken = (
  mutationOptions?: Options<GenerateRackBootstrapTokenData>
) => {
  return useMutation({
    ...mutationOptionsWithHeaders<
      GenerateRackBootstrapTokenResponses,
      GenerateRackBootstrapTokenErrors,
      GenerateRackBootstrapTokenData
    >(mutationOptions, generateRackBootstrapToken),
  });
};
