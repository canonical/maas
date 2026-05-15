import { useEffect } from "react";

import type { QueryClient } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";

import { IMAGES_WORKFLOW_KEY } from "@/app/api/query/images";
import type { ListSelectionStatusResponse } from "@/app/apiclient";
import {
  parseOptimisticImagesLocalStorage,
  registerPollingHook,
  silentPoll,
  startOrExtendSilentPolling,
} from "@/app/images/hooks/useOptimisticImages/utils/silentPolling";
import type { OptimisticImageStatusResponse } from "@/app/images/types";

type OptimisticMutateProps = {
  queryClient: QueryClient;
  imageId: number;
  action: "OptimisticDownloading" | "OptimisticStopping";
};

export type OptimisticMutateResult = {
  selectionStatusKey: readonly unknown[];
  previousSelectionStatuses?: ListSelectionStatusResponse;
  imageId: number;
};

type OptimisticOnErrorProps = {
  queryClient: QueryClient;
  onMutateResult: OptimisticMutateResult | undefined;
};

type OptimisticOnSuccessProps = {
  queryClient: QueryClient;
  onMutateResult: OptimisticMutateResult | undefined;
  action: "OptimisticDownloading" | "OptimisticStopping";
};

const optimisticMutate = async ({
  queryClient,
  imageId,
  action,
}: OptimisticMutateProps): Promise<OptimisticMutateResult> => {
  // Get data using predicate instead of exact key match
  const selectionStatusQueries =
    queryClient.getQueriesData<ListSelectionStatusResponse>({
      predicate: (query) => {
        const key = query.queryKey;
        return (
          Array.isArray(key) &&
          key[0] === IMAGES_WORKFLOW_KEY[0] &&
          typeof key[1] === "object" &&
          key[1]?._id === "listSelectionStatus"
        );
      },
    });

  const haltingSyncStatus: OptimisticImageStatusResponse["status"] =
    action === "OptimisticDownloading" ? "Waiting for download" : "Downloading";
  const haltingUpdateStatus: OptimisticImageStatusResponse["update_status"] =
    action === "OptimisticDownloading" ? "Update available" : "Downloading";

  const optimisticSyncOverride: Partial<
    Pick<OptimisticImageStatusResponse, "status" | "sync_percentage">
  > =
    action === "OptimisticDownloading"
      ? {
          status:
            "OptimisticDownloading" as OptimisticImageStatusResponse["status"],
          sync_percentage: 0,
        }
      : {
          status:
            "OptimisticStopping" as OptimisticImageStatusResponse["status"],
        };

  const optimisticUpdateOverride: Partial<
    Pick<OptimisticImageStatusResponse, "sync_percentage" | "update_status">
  > =
    action === "OptimisticDownloading"
      ? {
          update_status:
            "OptimisticDownloading" as OptimisticImageStatusResponse["update_status"],
          sync_percentage: 0,
        }
      : {
          update_status:
            "OptimisticStopping" as OptimisticImageStatusResponse["update_status"],
        };

  // Extract the actual query keys and data
  const [selectionStatusKey, previousSelectionStatuses] =
    selectionStatusQueries[0] || [null, null];

  // Optimistically update selection statuses to "Optimistic" or "Stopping"
  if (selectionStatusKey && previousSelectionStatuses) {
    const updatedSelectionStatuses = {
      ...previousSelectionStatuses,
      items: previousSelectionStatuses.items.map((item) => {
        if (item.id === imageId && item.status === haltingSyncStatus) {
          return {
            ...item,
            ...optimisticSyncOverride,
          };
        } else if (
          item.id === imageId &&
          item.update_status === haltingUpdateStatus
        ) {
          return {
            ...item,
            ...optimisticUpdateOverride,
          };
        }
        return item;
      }),
    };

    queryClient.setQueryData<
      Omit<ListSelectionStatusResponse, "items"> & {
        items: OptimisticImageStatusResponse[];
      }
    >(selectionStatusKey, updatedSelectionStatuses);
  }

  return {
    selectionStatusKey,
    previousSelectionStatuses,
    imageId,
  };
};

const optimisticOnError = ({
  queryClient,
  onMutateResult,
}: OptimisticOnErrorProps): void => {
  if (!onMutateResult) return;
  // Rollback to previous state if mutation fails
  if (
    onMutateResult?.selectionStatusKey &&
    onMutateResult?.previousSelectionStatuses
  ) {
    queryClient.setQueryData(
      onMutateResult.selectionStatusKey,
      onMutateResult.previousSelectionStatuses
    );
  }
};

const optimisticOnSuccess = ({
  queryClient,
  onMutateResult,
  action,
}: OptimisticOnSuccessProps): void => {
  if (!onMutateResult) return;

  const imageId = onMutateResult?.imageId;

  if (
    !silentPoll.entries.has(imageId) ||
    silentPoll.entries.get(imageId)?.action !== action
  ) {
    silentPoll.entries.set(imageId, { attempts: 0, action: action });
    const [startingImages, stoppingImages] = (
      localStorage.getItem("optimisticImages") ??
      "OptimisticDownloading=;OptimisticStopping="
    ).split(";");
    let startingImageIds = startingImages
      .replace("OptimisticDownloading=", "")
      .split(",")
      .filter((id) => id !== "")
      .map((id) => Number(id));
    let stoppingImageIds = stoppingImages
      .replace("OptimisticStopping=", "")
      .split(",")
      .filter((id) => id !== "")
      .map((id) => Number(id));
    // Ensure uniqueness by using Set
    if (action === "OptimisticDownloading") {
      startingImageIds = Array.from(new Set([...startingImageIds, imageId]));
    } else if (action === "OptimisticStopping") {
      stoppingImageIds = Array.from(new Set([...stoppingImageIds, imageId]));
    }
    localStorage.setItem(
      "optimisticImages",
      `OptimisticDownloading=${startingImageIds.join(",")};OptimisticStopping=${stoppingImageIds.join(",")}`
    );
  }

  startOrExtendSilentPolling(queryClient);
};

export const useOptimisticImages = (
  action: "OptimisticDownloading" | "OptimisticStopping"
) => {
  const queryClient = useQueryClient();

  const onMutateWithOptimisticImages = (
    imageId: number
  ): Promise<OptimisticMutateResult> => {
    return optimisticMutate({ queryClient, imageId, action });
  };

  const onErrorWithOptimisticImages = (
    onMutateResult: OptimisticMutateResult | undefined
  ): void => {
    optimisticOnError({ queryClient, onMutateResult });
  };

  const onSuccessWithOptimisticImages = (
    onMutateResult: OptimisticMutateResult
  ): void => {
    optimisticOnSuccess({ queryClient, onMutateResult, action });
  };

  const restoreOptimisticImages = async () => {
    const { startingImageIds, stoppingImageIds } =
      parseOptimisticImagesLocalStorage();

    // Only restore if there are images to restore
    if (startingImageIds.length === 0 && stoppingImageIds.length === 0) {
      return;
    }

    await Promise.allSettled(
      startingImageIds.map(async (imageId) => {
        const optimisticStartResult = await optimisticMutate({
          queryClient,
          imageId,
          action: "OptimisticDownloading",
        });
        optimisticOnSuccess({
          queryClient,
          onMutateResult: optimisticStartResult,
          action: "OptimisticDownloading",
        });
      })
    );

    await Promise.allSettled(
      stoppingImageIds.map(async (imageId) => {
        const optimisticStopResult = await optimisticMutate({
          queryClient,
          imageId,
          action: "OptimisticStopping",
        });
        optimisticOnSuccess({
          queryClient,
          onMutateResult: optimisticStopResult,
          action: "OptimisticStopping",
        });
      })
    );
  };

  useEffect(() => {
    return registerPollingHook();
  }, [queryClient]);

  return {
    onMutateWithOptimisticImages,
    onErrorWithOptimisticImages,
    onSuccessWithOptimisticImages,
    restoreOptimisticImages,
  };
};
