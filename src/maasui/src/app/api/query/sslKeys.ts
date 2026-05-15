import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useWebsocketAwareQuery } from "./base";

import {
  mutationOptionsWithHeaders,
  queryOptionsWithHeaders,
} from "@/app/api/utils";
import type {
  CreateUserSslkeyData,
  CreateUserSslkeyErrors,
  CreateUserSslkeyResponses,
  DeleteUserSslkeyData,
  DeleteUserSslkeyErrors,
  DeleteUserSslkeyResponses,
  GetUserSslkeysData,
  GetUserSslkeysErrors,
  GetUserSslkeysResponses,
  Options,
} from "@/app/apiclient";
import {
  deleteUserSslkey,
  createUserSslkey,
  getUserSslkeys,
} from "@/app/apiclient";
import { getUserSslkeysQueryKey } from "@/app/apiclient/@tanstack/react-query.gen";

export const useGetSslKeys = (options?: Options<GetUserSslkeysData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      GetUserSslkeysResponses,
      GetUserSslkeysErrors,
      GetUserSslkeysData
    >(options, getUserSslkeys, getUserSslkeysQueryKey(options))
  );
};

export const useCreateSslKeys = (
  mutationOptions?: Options<CreateUserSslkeyData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      CreateUserSslkeyResponses,
      CreateUserSslkeyErrors,
      CreateUserSslkeyData
    >(mutationOptions, createUserSslkey),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: getUserSslkeysQueryKey(),
      });
    },
  });
};

export const useDeleteSslKey = (
  mutationOptions?: Options<DeleteUserSslkeyData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      DeleteUserSslkeyResponses,
      DeleteUserSslkeyErrors,
      DeleteUserSslkeyData
    >(mutationOptions, deleteUserSslkey),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: getUserSslkeysQueryKey(),
      });
    },
  });
};
