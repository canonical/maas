import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useWebsocketAwareQuery } from "./base";

import {
  mutationOptionsWithHeaders,
  queryOptionsWithHeaders,
} from "@/app/api/utils";
import type {
  ImportUserSshkeysData,
  CreateUserSshkeysData,
  ListUserSshkeysData,
  DeleteUserSshkeyData,
  Options,
  ListUserSshkeysResponses,
  ListUserSshkeysErrors,
  CreateUserSshkeysResponses,
  CreateUserSshkeysErrors,
  ImportUserSshkeysResponses,
  ImportUserSshkeysErrors,
  DeleteUserSshkeyResponses,
  DeleteUserSshkeyErrors,
} from "@/app/apiclient";
import {
  deleteUserSshkey,
  importUserSshkeys,
  createUserSshkeys,
  listUserSshkeys,
} from "@/app/apiclient";
import { listUserSshkeysQueryKey } from "@/app/apiclient/@tanstack/react-query.gen";

export const useListSshKeys = (options?: Options<ListUserSshkeysData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      ListUserSshkeysResponses,
      ListUserSshkeysErrors,
      ListUserSshkeysData
    >(options, listUserSshkeys, listUserSshkeysQueryKey(options))
  );
};

export const useCreateSshKeys = (
  mutationOptions?: Options<CreateUserSshkeysData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      CreateUserSshkeysResponses,
      CreateUserSshkeysErrors,
      CreateUserSshkeysData
    >(mutationOptions, createUserSshkeys),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listUserSshkeysQueryKey(),
      });
    },
  });
};

export const useImportSshKeys = (
  mutationOptions?: Options<ImportUserSshkeysData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      ImportUserSshkeysResponses,
      ImportUserSshkeysErrors,
      ImportUserSshkeysData
    >(mutationOptions, importUserSshkeys),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listUserSshkeysQueryKey(),
      });
    },
  });
};

export const useDeleteSshKey = (
  mutationOptions?: Options<DeleteUserSshkeyData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      DeleteUserSshkeyResponses,
      DeleteUserSshkeyErrors,
      DeleteUserSshkeyData
    >(mutationOptions, deleteUserSshkey),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listUserSshkeysQueryKey(),
      });
    },
  });
};
