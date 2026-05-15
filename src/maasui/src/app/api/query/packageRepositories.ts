import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useWebsocketAwareQuery } from "./base";

import {
  mutationOptionsWithHeaders,
  queryOptionsWithHeaders,
} from "@/app/api/utils";
import type {
  CreatePackageRepositoryData,
  CreatePackageRepositoryErrors,
  CreatePackageRepositoryResponses,
  DeletePackageRepositoryData,
  DeletePackageRepositoryErrors,
  DeletePackageRepositoryResponses,
  GetPackageRepositoryData,
  GetPackageRepositoryErrors,
  GetPackageRepositoryResponses,
  ListPackageRepositoriesData,
  ListPackageRepositoriesErrors,
  ListPackageRepositoriesResponses,
  Options,
  UpdatePackageRepositoryData,
  UpdatePackageRepositoryErrors,
  UpdatePackageRepositoryResponses,
} from "@/app/apiclient";
import {
  createPackageRepository,
  deletePackageRepository,
  getPackageRepository,
  listPackageRepositories,
  updatePackageRepository,
} from "@/app/apiclient";
import {
  getPackageRepositoryQueryKey,
  listPackageRepositoriesQueryKey,
} from "@/app/apiclient/@tanstack/react-query.gen";

export const usePackageRepositories = (
  options?: Options<ListPackageRepositoriesData>
) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      ListPackageRepositoriesResponses,
      ListPackageRepositoriesErrors,
      ListPackageRepositoriesData
    >(
      options,
      listPackageRepositories,
      listPackageRepositoriesQueryKey(options)
    )
  );
};

export const useGetPackageRepository = (
  options: Options<GetPackageRepositoryData>
) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      GetPackageRepositoryResponses,
      GetPackageRepositoryErrors,
      GetPackageRepositoryData
    >(options, getPackageRepository, getPackageRepositoryQueryKey(options))
  );
};

export const useCreatePackageRepository = (
  mutationOptions?: Options<CreatePackageRepositoryData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      CreatePackageRepositoryResponses,
      CreatePackageRepositoryErrors,
      CreatePackageRepositoryData
    >(mutationOptions, createPackageRepository),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listPackageRepositoriesQueryKey(),
      });
    },
  });
};

export const useUpdatePackageRepository = (
  mutationOptions?: Options<UpdatePackageRepositoryData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      UpdatePackageRepositoryResponses,
      UpdatePackageRepositoryErrors,
      UpdatePackageRepositoryData
    >(mutationOptions, updatePackageRepository),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listPackageRepositoriesQueryKey(),
      });
    },
  });
};

export const useDeletePackageRepository = (
  mutationOptions?: Options<DeletePackageRepositoryData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      DeletePackageRepositoryResponses,
      DeletePackageRepositoryErrors,
      DeletePackageRepositoryData
    >(mutationOptions, deletePackageRepository),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listPackageRepositoriesQueryKey(),
      });
    },
  });
};
