import { useMutation } from "@tanstack/react-query";

import { mutationOptionsWithHeaders } from "@/app/api/utils";
import type {
  Options,
  SyncBootsourceBootsourceselectionData,
  SyncBootsourceBootsourceselectionErrors,
  SyncBootsourceBootsourceselectionResponses,
  StopSyncBootsourceBootsourceselectionData,
  StopSyncBootsourceBootsourceselectionErrors,
  StopSyncBootsourceBootsourceselectionResponses,
} from "@/app/apiclient";
import {
  syncBootsourceBootsourceselection,
  stopSyncBootsourceBootsourceselection,
} from "@/app/apiclient";
import type { OptimisticMutateResult } from "@/app/images/hooks/useOptimisticImages/useOptimisticImages";
import { useOptimisticImages } from "@/app/images/hooks/useOptimisticImages/useOptimisticImages";

export const useStartImageSync = (
  mutationOptions?: Options<SyncBootsourceBootsourceselectionData>
) => {
  const {
    onMutateWithOptimisticImages,
    onErrorWithOptimisticImages,
    onSuccessWithOptimisticImages,
  } = useOptimisticImages("OptimisticDownloading");

  return useMutation({
    ...mutationOptionsWithHeaders<
      SyncBootsourceBootsourceselectionResponses,
      SyncBootsourceBootsourceselectionErrors,
      SyncBootsourceBootsourceselectionData
    >(mutationOptions, syncBootsourceBootsourceselection),
    onMutate: async (variables): Promise<OptimisticMutateResult> => {
      const imageId = variables.path.id;
      return onMutateWithOptimisticImages(imageId);
    },
    onError: (
      _err,
      _variables,
      onMutateResult: OptimisticMutateResult | undefined,
      _context
    ) => {
      onErrorWithOptimisticImages(onMutateResult);
    },
    onSuccess: async (
      _data,
      _variables,
      onMutateResult: OptimisticMutateResult,
      _context
    ) => {
      onSuccessWithOptimisticImages(onMutateResult);
    },
  });
};

export const useStopImageSync = (
  mutationOptions?: Options<StopSyncBootsourceBootsourceselectionData>
) => {
  const {
    onMutateWithOptimisticImages,
    onErrorWithOptimisticImages,
    onSuccessWithOptimisticImages,
  } = useOptimisticImages("OptimisticStopping");

  return useMutation({
    ...mutationOptionsWithHeaders<
      StopSyncBootsourceBootsourceselectionResponses,
      StopSyncBootsourceBootsourceselectionErrors,
      StopSyncBootsourceBootsourceselectionData
    >(mutationOptions, stopSyncBootsourceBootsourceselection),
    onMutate: async (variables): Promise<OptimisticMutateResult> => {
      const imageId = variables.path.id;
      return onMutateWithOptimisticImages(imageId);
    },
    onError: (
      _err,
      _variables,
      onMutateResult: OptimisticMutateResult | undefined,
      _context
    ) => {
      onErrorWithOptimisticImages(onMutateResult);
    },
    onSuccess: async (
      _data,
      _variables,
      onMutateResult: OptimisticMutateResult,
      _context
    ) => {
      onSuccessWithOptimisticImages(onMutateResult);
    },
  });
};
