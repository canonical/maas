import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useWebsocketAwareQuery } from "@/app/api/query/base";
import { IMAGES_WORKFLOW_KEY } from "@/app/api/query/images";
import {
  mutationOptionsWithHeaders,
  queryOptionsWithHeaders,
} from "@/app/api/utils";
import type {
  GetBootsourceData,
  GetBootsourceErrors,
  GetBootsourceResponses,
  ListBootsourcesData,
  ListBootsourcesErrors,
  ListBootsourcesResponses,
  Options,
  DeleteBootsourceErrors,
  CreateBootsourceData,
  CreateBootsourceErrors,
  CreateBootsourceResponses,
  UpdateBootsourceData,
  UpdateBootsourceResponses,
  UpdateBootsourceErrors,
  FetchBootsourcesAvailableImagesData,
  FetchBootsourcesAvailableImagesResponses,
  FetchBootsourcesAvailableImagesErrors,
  DeleteBootsourceData,
  DeleteBootsourceResponses,
} from "@/app/apiclient";
import {
  updateBootsource,
  createBootsource,
  deleteBootsource,
  fetchBootsourcesAvailableImages,
  getBootsource,
  listBootsources,
} from "@/app/apiclient";
import {
  getAllAvailableImagesQueryKey,
  getBootsourceQueryKey,
  listBootsourcesQueryKey,
} from "@/app/apiclient/@tanstack/react-query.gen";

export const useImageSources = (options?: Options<ListBootsourcesData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<
      ListBootsourcesResponses,
      ListBootsourcesErrors,
      ListBootsourcesData
    >(options, listBootsources, listBootsourcesQueryKey(options))
  );
};

export const useGetImageSource = (
  options: Options<GetBootsourceData>,
  enabled: boolean
) => {
  return useWebsocketAwareQuery({
    ...queryOptionsWithHeaders<
      GetBootsourceResponses,
      GetBootsourceErrors,
      GetBootsourceData
    >(options, getBootsource, getBootsourceQueryKey(options)),
    enabled,
  });
};

export const useChangeImageSource = () => {
  const queryClient = useQueryClient();

  return useMutation<
    CreateBootsourceResponses[keyof CreateBootsourceResponses],
    | CreateBootsourceErrors[keyof CreateBootsourceErrors]
    | DeleteBootsourceErrors[keyof DeleteBootsourceErrors],
    Options<CreateBootsourceData & { body: { current_boot_source_id: number } }>
  >({
    mutationFn: async (params) => {
      // Step 1: Create new source
      const createResult = await createBootsource({
        ...params,
        throwOnError: true,
      });

      // Step 2: Delete old source
      await deleteBootsource({
        path: { boot_source_id: params.body.current_boot_source_id },
        throwOnError: true,
      });

      return createResult.data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: listBootsourcesQueryKey(),
      });
      await queryClient.invalidateQueries({
        queryKey: IMAGES_WORKFLOW_KEY,
      });
      await queryClient.invalidateQueries({
        queryKey: getAllAvailableImagesQueryKey(),
      });
    },
  });
};

export const useCreateImageSource = (
  mutationOptions?: Options<CreateBootsourceData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      CreateBootsourceResponses,
      CreateBootsourceErrors,
      CreateBootsourceData
    >(mutationOptions, createBootsource),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listBootsourcesQueryKey(),
      });
    },
  });
};

export const useUpdateImageSource = (
  mutationOptions?: Options<UpdateBootsourceData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      UpdateBootsourceResponses,
      UpdateBootsourceErrors,
      UpdateBootsourceData
    >(mutationOptions, updateBootsource),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listBootsourcesQueryKey(),
      });
    },
  });
};

export const useDeleteImageSource = (
  mutationOptions?: Options<DeleteBootsourceData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      DeleteBootsourceResponses,
      DeleteBootsourceErrors,
      DeleteBootsourceData
    >(mutationOptions, deleteBootsource),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listBootsourcesQueryKey(),
      });
    },
  });
};

export const useFetchImageSource = (
  mutationOptions?: Options<FetchBootsourcesAvailableImagesData>
) => {
  return useMutation({
    ...mutationOptionsWithHeaders<
      FetchBootsourcesAvailableImagesResponses,
      FetchBootsourcesAvailableImagesErrors,
      FetchBootsourcesAvailableImagesData
    >(mutationOptions, fetchBootsourcesAvailableImages),
  });
};
