import type { ReactElement } from "react";

import { ContentSection } from "@canonical/maas-react-components";
import {
  Icon,
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";
import { formatDuration } from "date-fns";
import * as Yup from "yup";

import {
  useConfigurations,
  useBulkSetConfigurations,
} from "@/app/api/query/configurations";
import type { PublicConfigName, SetConfigurationsError } from "@/app/apiclient";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { useLogout } from "@/app/base/hooks/logout";
import { configActions } from "@/app/store/config";
import { ConfigNames } from "@/app/store/config/types";
import {
  humanReadableToSeconds,
  secondsToDuration,
} from "@/app/utils/timeSpan";

type TokenExpirationFormValues = {
  refresh_token_expiration: string;
};

export enum Labels {
  Loading = "Loading...",
  Expiration = "Refresh token expiration",
  Save = "Save",
  ConfigureTokenExpiration = "Configure Token Expiration",
}

const TokenExpirationSchema = Yup.object().shape({
  refresh_token_expiration: Yup.string()
    .required("Timeout length is required")
    .matches(
      /^((\d)+ ?(hour|day|week|minute)(s)? ?(and)? ?)+$/,
      "Unit must be `string` type with a value of weeks, days, hours, and/or minutes."
    )
    .test(
      "session-length-boundary-check",
      "Maximum value is 60 days (or equivalent)",
      function (value) {
        if (!value) {
          return false;
        }

        const sessionLengthInSeconds = humanReadableToSeconds(value);
        if (!sessionLengthInSeconds) {
          return false;
        }

        return sessionLengthInSeconds <= 5184000;
      }
    )
    .test(
      "session-length-minimum-check",
      "Minimum value is 10 minutes (or equivalent)",
      function (value) {
        if (!value) {
          return false;
        }
        const sessionLengthInSeconds = humanReadableToSeconds(value);
        if (!sessionLengthInSeconds) {
          return false;
        }

        return sessionLengthInSeconds >= 600;
      }
    ),
});

const SessionTimeout = (): ReactElement => {
  const names = [ConfigNames.REFRESH_TOKEN_DURATION] as PublicConfigName[];
  const { data, isPending, error } = useConfigurations({
    query: { name: names },
  });
  const eTag = data?.headers?.get("ETag");
  const token_expiration = data?.items?.[0].value || {};
  const updateConfig = useBulkSetConfigurations();
  useWindowTitle("Token Expiration");
  const logout = useLogout();

  if (isPending) {
    return <Spinner aria-label={Labels.Loading} text={Labels.Loading} />;
  }

  return (
    <PageContent>
      <ContentSection variant="narrow">
        <ContentSection.Title className="section-header__title">
          Token expiration
        </ContentSection.Title>
        <ContentSection.Content>
          {error && (
            <NotificationBanner
              severity="negative"
              title="Error while fetching setting security configurations token expiration"
            >
              {error.message}
            </NotificationBanner>
          )}
          <FormikForm<TokenExpirationFormValues, SetConfigurationsError>
            aria-label={Labels.ConfigureTokenExpiration}
            cleanup={configActions.cleanup}
            errors={updateConfig.error}
            initialValues={{
              refresh_token_expiration: formatDuration(
                secondsToDuration(token_expiration as number)
              ),
            }}
            onSaveAnalytics={{
              action: "Saved",
              category: "Security settings",
              label: "Token expiration form",
            }}
            onSubmit={(values, { resetForm }) => {
              const tokenExpirationInSeconds = humanReadableToSeconds(
                values.refresh_token_expiration
              );
              tokenExpirationInSeconds &&
                updateConfig.mutate(
                  {
                    headers: {
                      ETag: eTag,
                    },
                    body: {
                      configurations: [
                        {
                          name: ConfigNames.REFRESH_TOKEN_DURATION,
                          value: tokenExpirationInSeconds,
                        },
                      ],
                    },
                  },
                  {
                    onSuccess: logout,
                  }
                );

              resetForm({ values });
            }}
            resetOnSave
            saved={updateConfig.isSuccess}
            saving={updateConfig.isPending}
            validationSchema={TokenExpirationSchema}
          >
            <FormikField
              help={
                <span>
                  Maximum refresh token duration is 60 days. Format options are
                  weeks, days, hours, and/or minutes.
                  <br />
                  <br />
                  <Icon name="warning" /> MAAS will automatically log out all
                  users after changing the refresh token duration. New token
                  duration applies after login.
                  <br />
                  <br />
                  <Icon name="warning" /> This setting applies to local MAAS
                  users. Externally authenticated users, such as those using
                  Single Sign-On, may have different token expiration policies.
                  Configure those settings in your identity provider.
                </span>
              }
              label={Labels.Expiration}
              name="refresh_token_expiration"
              required={true}
              type="text"
            />
          </FormikForm>
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default SessionTimeout;
