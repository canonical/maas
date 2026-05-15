import type { UseQueryResult } from "@tanstack/react-query";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useWebsocketAwareQuery } from "@/app/api/query/base";
import type { WithHeaders } from "@/app/api/utils";
import {
  mutationOptionsWithHeaders,
  queryOptionsWithHeaders,
} from "@/app/api/utils";
import type {
  CreateUserData,
  CreateUserErrors,
  CreateUserResponses,
  DeleteUserData,
  DeleteUserErrors,
  DeleteUserResponses,
  GetUserData,
  GetUserErrors,
  GetUserResponses,
  ListUsersData,
  ListUsersError,
  ListUsersErrors,
  ListUsersResponses,
  ListUsersStatisticsData,
  ListUsersStatisticsError,
  ListUsersStatisticsErrors,
  ListUsersStatisticsResponses,
  Options,
  UpdateUserData,
  UpdateUserErrors,
  UpdateUserResponses,
  UserResponse,
  UserStatisticsResponse,
} from "@/app/apiclient";
import {
  createUser,
  deleteUser,
  getUser,
  listUsers,
  listUsersStatistics,
  updateUser,
} from "@/app/apiclient";
import {
  getUserQueryKey,
  listUsersQueryKey,
  listUsersStatisticsQueryKey,
} from "@/app/apiclient/@tanstack/react-query.gen";

export type UserWithStatistics = WithHeaders<UserResponse> & {
  statistics: UserStatisticsResponse | undefined;
};

export type UseUsersResult = {
  data:
    | {
        items: UserWithStatistics[];
        total: number;
      }
    | undefined;
  isPending: UseQueryResult["isPending"];
  statisticsPending: UseQueryResult["isPending"];
  isSuccess: UseQueryResult["isSuccess"];
  isError: UseQueryResult["isError"];
  error: ListUsersError | null;
  statisticsError: ListUsersStatisticsError | null;
};

export const useUsers = (options?: Options<ListUsersData>): UseUsersResult => {
  const users = useWebsocketAwareQuery(
    queryOptionsWithHeaders<ListUsersResponses, ListUsersErrors, ListUsersData>(
      options,
      listUsers,
      listUsersQueryKey(options)
    )
  );
  const userIds = users.data?.items.map((user) => user.id) ?? [];
  const statistics = useUsersStatistics({
    query: { id: userIds },
  });

  return {
    ...users,
    statisticsPending: statistics.isPending,
    data: users.data
      ? {
          ...users.data,
          items: users.data.items.map((user) => ({
            ...user,
            statistics: statistics.data?.items.find(
              (stat) => stat.id === user.id
            ),
          })),
        }
      : undefined,
    error: users.error,
    statisticsError: statistics.error,
  };
};

export const useUsersStatistics = (
  options?: Options<ListUsersStatisticsData>,
  enabled?: boolean
) => {
  return useWebsocketAwareQuery({
    ...queryOptionsWithHeaders<
      ListUsersStatisticsResponses,
      ListUsersStatisticsErrors,
      ListUsersStatisticsData
    >(options, listUsersStatistics, listUsersStatisticsQueryKey(options)),
    enabled,
  });
};

export const useUserCount = (options?: Options<ListUsersData>) => {
  return useWebsocketAwareQuery({
    ...queryOptionsWithHeaders<
      ListUsersResponses,
      ListUsersErrors,
      ListUsersData
    >(options, listUsers, listUsersQueryKey(options)),
    select: (data) => data?.total ?? 0,
  });
};

export const useGetUser = (options: Options<GetUserData>) => {
  return useWebsocketAwareQuery(
    queryOptionsWithHeaders<GetUserResponses, GetUserErrors, GetUserData>(
      options,
      getUser,
      getUserQueryKey(options)
    )
  );
};

export const useCreateUser = (mutationOptions?: Options<CreateUserData>) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      CreateUserResponses,
      CreateUserErrors,
      CreateUserData
    >(mutationOptions, createUser),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listUsersQueryKey(),
      });
    },
  });
};

export const useUpdateUser = (mutationOptions?: Options<UpdateUserData>) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      UpdateUserResponses,
      UpdateUserErrors,
      UpdateUserData
    >(mutationOptions, updateUser),
    onSuccess: async () => {
      return queryClient.invalidateQueries({
        queryKey: listUsersQueryKey(),
      });
    },
  });
};

export const useDeleteUser = (mutationOptions?: Options<DeleteUserData>) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      DeleteUserResponses,
      DeleteUserErrors,
      DeleteUserData
    >(mutationOptions, deleteUser),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: listUsersQueryKey(),
      });
    },
  });
};
