import { useMemo } from "react";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useDispatch } from "react-redux";

import { useWebsocketAwareQuery } from "@/app/api/query/base";
import type { UserWithStatistics } from "@/app/api/query/users";
import {
  mutationOptionsWithHeaders,
  queryOptionsWithHeaders,
} from "@/app/api/utils";
import type {
  CompleteIntroData,
  CompleteIntroErrors,
  CompleteIntroResponses,
  CreateOauthProviderData,
  CreateOauthProviderErrors,
  CreateOauthProviderResponses,
  CreateSessionData,
  CreateSessionErrors,
  CreateSessionResponses,
  DeleteOauthProviderData,
  DeleteOauthProviderErrors,
  DeleteOauthProviderResponses,
  ExtendSessionData,
  ExtendSessionErrors,
  ExtendSessionResponses,
  GetMeStatisticsData,
  GetMeStatisticsError,
  GetMeStatisticsErrors,
  GetMeStatisticsResponses,
  GetOauthProviderData,
  GetOauthProviderErrors,
  GetOauthProviderResponses,
  GetUserInfoData,
  GetUserInfoError,
  GetUserInfoErrors,
  GetUserInfoResponses,
  HandleOauthCallbackData,
  HandleOauthCallbackErrors,
  HandleOauthCallbackResponses,
  InitiateAuthFlowData,
  InitiateAuthFlowErrors,
  InitiateAuthFlowResponses,
  LoginData,
  LoginError,
  LoginErrors,
  LoginResponses,
  Options,
  PreLoginData,
  PreLoginErrors,
  PreLoginResponses,
  TokenResponse,
  UpdateOauthProviderData,
  UpdateOauthProviderErrors,
  UpdateOauthProviderResponses,
} from "@/app/apiclient";
import {
  completeIntro,
  createOauthProvider,
  createSession,
  deleteOauthProvider,
  extendSession,
  getMeStatistics,
  getOauthProvider,
  getUserInfo,
  handleOauthCallback,
  initiateAuthFlow,
  login,
  preLogin,
  updateOauthProvider,
} from "@/app/apiclient";
import {
  getMeStatisticsQueryKey,
  getOauthProviderQueryKey,
  getUserInfoQueryKey,
  handleOauthCallbackQueryKey,
  initiateAuthFlowQueryKey,
} from "@/app/apiclient/@tanstack/react-query.gen";
import { Labels } from "@/app/login/Login/Login";
import { statusActions } from "@/app/store/status";
import { setCookie } from "@/app/utils";
import { COOKIE_NAMES } from "@/app/utils/cookies";

export const usePreLogin = (mutationOptions?: Options<PreLoginData>) => {
  return useMutation({
    ...mutationOptionsWithHeaders<
      PreLoginResponses,
      PreLoginErrors,
      PreLoginData
    >(mutationOptions, preLogin),
  });
};

type OIDCLoginStep = "OIDC" | "PASSWORD" | "USERNAME";

type OIDCLoginState = {
  step: OIDCLoginStep;
  oidcURL: string;
  providerName: string;
  isPending?: boolean;
  error?: "UNKNOWN" | "USER_NOT_FOUND";
};

export const useIsOIDCUser = (
  options: Options<InitiateAuthFlowData>,
  enabled: boolean
) => {
  const dispatch = useDispatch();
  const query = useWebsocketAwareQuery({
    ...queryOptionsWithHeaders<
      InitiateAuthFlowResponses,
      InitiateAuthFlowErrors,
      InitiateAuthFlowData
    >(options, initiateAuthFlow, initiateAuthFlowQueryKey(options)),
    enabled,
    refetchOnWindowFocus: false,
    retry: false,
  });

  const loginState = useMemo<OIDCLoginState>(() => {
    if (!enabled || query.isPending) {
      return {
        step: "USERNAME",
        oidcURL: "",
        providerName: "",
        isPending: enabled ? query.isPending : false,
      };
    }

    if (query.error) {
      const { code } = query.error;
      dispatch(
        statusActions.loginError(
          code === 409 ? Labels.MissingProviderConfig : Labels.UnknownError
        )
      );
      return {
        step: "USERNAME",
        oidcURL: "",
        providerName: "",
        error: code === 409 ? "USER_NOT_FOUND" : "UNKNOWN",
      };
    }

    if (!query.data) {
      dispatch(statusActions.loginError(Labels.UnknownError));
      return {
        step: "USERNAME",
        oidcURL: "",
        providerName: "",
        error: "UNKNOWN",
      };
    }

    const { is_oidc, auth_url, provider_name } = query.data;

    if (is_oidc) {
      return {
        step: "OIDC",
        oidcURL: auth_url ?? "",
        providerName: provider_name ?? "",
      };
    }

    return {
      step: "PASSWORD",
      oidcURL: "",
      providerName: "",
    };
  }, [enabled, query.data, query.error, query.isPending, dispatch]);

  return {
    ...query,
    loginState,
  };
};

export const useGetCallback = (
  options: Options<HandleOauthCallbackData>,
  enabled: boolean
) => {
  return useWebsocketAwareQuery({
    ...queryOptionsWithHeaders<
      HandleOauthCallbackResponses,
      HandleOauthCallbackErrors,
      HandleOauthCallbackData
    >(options, handleOauthCallback, handleOauthCallbackQueryKey(options)),
    refetchOnWindowFocus: false,
    retry: false,
    enabled,
  });
};

export const useAuthenticate = (mutationOptions?: Options<LoginData>) => {
  const dispatch = useDispatch();
  const createSession = useCreateSession();
  return useMutation({
    ...mutationOptionsWithHeaders<LoginResponses, LoginErrors, LoginData>(
      mutationOptions,
      login
    ),
    onSuccess: async (data: TokenResponse) => {
      setCookie(COOKIE_NAMES.LOCAL_JWT_TOKEN_NAME, data.access_token, {
        sameSite: "Strict",
        path: "/",
      });
      setCookie(COOKIE_NAMES.LOCAL_REFRESH_TOKEN_NAME, data.refresh_token!, {
        sameSite: "Strict",
        path: "/",
      });
      await createSession.mutateAsync({});
      dispatch(statusActions.loginSuccess());
    },
    onError: (error: LoginError) => {
      if (error.code === 401) {
        dispatch(statusActions.loginError(Labels.IncorrectCredentials));
      }
    },
  });
};

export const useCreateSession = (
  mutationOtions?: Options<CreateSessionData>
) => {
  return useMutation({
    ...mutationOptionsWithHeaders<
      CreateSessionResponses,
      CreateSessionErrors,
      CreateSessionData
    >(mutationOtions, createSession),
  });
};

export const useExtendSession = (
  mutationOptions?: Options<ExtendSessionData>
) => {
  return useMutation({
    ...mutationOptionsWithHeaders<
      ExtendSessionResponses,
      ExtendSessionErrors,
      ExtendSessionData
    >(mutationOptions, extendSession),
  });
};

export const useGetCurrentUser = (
  options?: Options<GetUserInfoData>
): {
  data: UserWithStatistics | undefined;
  isPending: boolean;
  isSuccess: boolean;
  isError: boolean;
  error: GetUserInfoError | null;
  statisticsError: GetMeStatisticsError | null;
} => {
  const userInfo = useWebsocketAwareQuery({
    ...queryOptionsWithHeaders<
      GetUserInfoResponses,
      GetUserInfoErrors,
      GetUserInfoData
    >(options, getUserInfo, getUserInfoQueryKey(options)),
    retry: false, // explicitly set retry to false
  });

  const statistics = useWebsocketAwareQuery({
    ...queryOptionsWithHeaders<
      GetMeStatisticsResponses,
      GetMeStatisticsErrors,
      GetMeStatisticsData
    >({}, getMeStatistics, getMeStatisticsQueryKey()),
    enabled: userInfo.isSuccess,
    retry: false,
  });

  return {
    ...userInfo,
    data: userInfo.data
      ? ({
          ...userInfo.data,
          statistics: statistics.data,
        } as UserWithStatistics)
      : undefined,
    error: userInfo.error,
    statisticsError: statistics.error,
  };
};

export const useGetIsSuperUser = (options?: Options<GetUserInfoData>) => {
  return useWebsocketAwareQuery({
    ...queryOptionsWithHeaders<
      GetUserInfoResponses,
      GetUserInfoErrors,
      GetUserInfoData
    >(options, getUserInfo, getUserInfoQueryKey(options)),
    select: (data) => data.is_superuser,
  });
};

export const useCompleteIntro = (
  mutationOptions?: Options<CompleteIntroData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      CompleteIntroResponses,
      CompleteIntroErrors,
      CompleteIntroData
    >(mutationOptions, completeIntro),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: getUserInfoQueryKey(),
      });
    },
  });
};

export const useActiveOauthProvider = (
  options?: Options<GetOauthProviderData>
) => {
  return useWebsocketAwareQuery({
    ...queryOptionsWithHeaders<
      GetOauthProviderResponses,
      GetOauthProviderErrors,
      GetOauthProviderData
    >(options, getOauthProvider, getOauthProviderQueryKey(options)),
    refetchOnWindowFocus: false,
    retry: false,
  });
};

export const useCreateOauthProvider = (
  mutationOptions?: Options<CreateOauthProviderData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      CreateOauthProviderResponses,
      CreateOauthProviderErrors,
      CreateOauthProviderData
    >(mutationOptions, createOauthProvider),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: getOauthProviderQueryKey(),
      });
    },
  });
};

export const useUpdateOauthProvider = (
  mutationOptions?: Options<UpdateOauthProviderData>
) => {
  return useMutation({
    ...mutationOptionsWithHeaders<
      UpdateOauthProviderResponses,
      UpdateOauthProviderErrors,
      UpdateOauthProviderData
    >(mutationOptions, updateOauthProvider),
  });
};

export const useDeleteOauthProvider = (
  mutationOptions?: Options<DeleteOauthProviderData>
) => {
  const queryClient = useQueryClient();
  return useMutation({
    ...mutationOptionsWithHeaders<
      DeleteOauthProviderResponses,
      DeleteOauthProviderErrors,
      DeleteOauthProviderData
    >(mutationOptions, deleteOauthProvider),
    onSuccess: () => {
      return queryClient.invalidateQueries({
        queryKey: getOauthProviderQueryKey(),
      });
    },
  });
};
