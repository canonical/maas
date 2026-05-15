import { useState, type ReactElement } from "react";

import { useQueryClient } from "@tanstack/react-query";
import * as Yup from "yup";

import SingleSignOnFormFields from "./SingleSignOnFormFields/SingleSignOnFormFields";
import type { SingleSignOnFormValues } from "./types";

import {
  useCreateOauthProvider,
  useUpdateOauthProvider,
} from "@/app/api/query/auth";
import type { WithHeaders } from "@/app/api/utils";
import type {
  OAuthProviderResponse,
  OAuthTokenTypeChoices,
} from "@/app/apiclient";
import { getOauthProviderQueryKey } from "@/app/apiclient/@tanstack/react-query.gen";
import FormikForm from "@/app/base/components/FormikForm";

type Props = {
  provider: WithHeaders<OAuthProviderResponse> | undefined;
  maasURL: string;
};

const SingleSignOnSchema = Yup.object().shape({
  name: Yup.string().required("Name is a required field."),
  client_id: Yup.string().required("Client ID is a required field."),
  client_secret: Yup.string().required("Client secret is a required field."),
  issuer_url: Yup.string().required("Issuer URL is a required field."),
  redirect_uri: Yup.string().required("Redirect URL is a required field."),
  scopes: Yup.string().required("Scopes is a required field."),
  token_type: Yup.mixed<OAuthTokenTypeChoices>()
    .oneOf(["JWT", "Opaque"])
    .required("Token type is a required field."),
});

const SingleSignOnForm = ({ provider, maasURL }: Props): ReactElement => {
  const [initialValues, setInitialValues] = useState<SingleSignOnFormValues>(
    provider ?? {
      name: "",
      client_id: "",
      client_secret: "",
      issuer_url: "",
      redirect_uri: maasURL + "/r/login/oidc/callback",
      scopes: "",
      token_type: "JWT",
    }
  );

  const eTag = provider?.headers?.get("ETag");

  const createOauthProvider = useCreateOauthProvider();
  const updateOauthProvider = useUpdateOauthProvider();
  const queryClient = useQueryClient();

  const handleCancel = () => {
    setInitialValues(
      provider ?? {
        name: "",
        client_id: "",
        client_secret: "",
        issuer_url: "",
        redirect_uri: maasURL + "/r/login/oidc/callback",
        scopes: "",
        token_type: "JWT",
      }
    );
  };

  const handleSubmit = (values: SingleSignOnFormValues) => {
    if (provider) {
      updateOauthProvider.mutate(
        {
          headers: {
            ETag: eTag,
          },
          body: {
            name: values.name,
            client_id: values.client_id,
            client_secret: values.client_secret,
            redirect_uri: values.redirect_uri,
            issuer_url: values.issuer_url,
            scopes: values.scopes,
            enabled: true,
            token_type: values.token_type as OAuthTokenTypeChoices,
          },
          path: { provider_id: provider.id },
        },
        {
          onSuccess: () => {
            return queryClient.invalidateQueries({
              queryKey: getOauthProviderQueryKey(),
            });
          },
        }
      );
    } else {
      createOauthProvider.mutate({
        body: {
          name: values.name,
          client_id: values.client_id,
          client_secret: values.client_secret,
          redirect_uri: values.redirect_uri,
          issuer_url: values.issuer_url,
          scopes: values.scopes,
          enabled: true,
          token_type: values.token_type as OAuthTokenTypeChoices,
        },
      });
    }
  };

  return (
    <FormikForm
      aria-label="Single sign-on form"
      errors={createOauthProvider.error || updateOauthProvider.error}
      initialValues={initialValues}
      onCancel={(_, { resetForm }) => {
        resetForm();
        handleCancel();
      }}
      onSubmit={handleSubmit}
      saved={createOauthProvider.isSuccess || updateOauthProvider.isSuccess}
      saving={createOauthProvider.isPending || updateOauthProvider.isPending}
      validationSchema={SingleSignOnSchema}
    >
      <SingleSignOnFormFields maasURL={maasURL} provider={provider} />
    </FormikForm>
  );
};

export default SingleSignOnForm;
