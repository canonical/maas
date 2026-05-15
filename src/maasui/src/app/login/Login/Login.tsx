import type { ReactElement } from "react";
import { useCallback, useEffect, useState } from "react";

import {
  Button,
  Card,
  Code,
  Col,
  Notification as NotificationBanner,
  Row,
  Strip,
} from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate, useSearchParams } from "react-router";
import * as Yup from "yup";

import { useAuthenticate, useIsOIDCUser } from "@/app/api/query/auth";
import type { LoginError } from "@/app/apiclient";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import { statusActions } from "@/app/store/status";
import statusSelectors from "@/app/store/status/selectors";
import { formatErrors } from "@/app/utils";

const generateSchema = (requirePassword: boolean) =>
  Yup.object({
    username: Yup.string().required("Username is required"),
    password: requirePassword
      ? Yup.string().required("Password is required")
      : Yup.string(),
  });

export type LoginValues = {
  password: string;
  username: string;
};

export const Labels = {
  APILoginForm: "Login",
  ExternalLoginButton: "Go to login page",
  NoUsers: "No admin user has been created yet",
  Password: "Password",
  Submit: "Login",
  Username: "Username",
  IncorrectCredentials:
    "Please enter a correct username and password. Note that both fields may be case-sensitive.",
  MissingProviderConfig:
    "The username belongs to an OIDC user, but the corresponding OIDC provider is disabled or misconfigured.",
  UnknownError: "Something went wrong. Please try again.",
} as const;

type LoginStep = "OIDC" | "PASSWORD" | "USERNAME";

export const Login = (): ReactElement => {
  const dispatch = useDispatch();
  const externalAuthURL = useSelector(statusSelectors.externalAuthURL);
  const externalLoginURL = useSelector(statusSelectors.externalLoginURL);
  const authenticationError = useSelector(statusSelectors.authenticationError);
  const noUsers = useSelector(statusSelectors.noUsers);

  const [searchParams] = useSearchParams();
  const redirect = searchParams.get("redirectTo");
  const authenticate = useAuthenticate();
  const [submittedUsername, setSubmittedUsername] = useState<string | null>(
    null
  );

  const { loginState } = useIsOIDCUser(
    {
      query: {
        email: submittedUsername ?? "",
        redirect_target: redirect ?? "/machines",
      },
    },
    Boolean(submittedUsername)
  );

  const step: LoginStep = loginState.step;
  const hasEnteredUsername = step !== "USERNAME";
  const requirePassword = step === "PASSWORD";
  const isOIDCUser = step === "OIDC";

  const navigate = useNavigate();

  const handleRedirect = useCallback(() => {
    // send user back to the page they tried to visit
    // { replace: true } avoids going back to login page once authenticated
    navigate(redirect ?? urls.machines.index, {
      replace: true,
    });
  }, [navigate, redirect]);

  useEffect(() => {
    if (authenticate.isSuccess) {
      handleRedirect();
    }
  }, [authenticate.isSuccess, handleRedirect]);

  useWindowTitle("Login");

  useEffect(() => {
    if (externalAuthURL) {
      dispatch(statusActions.externalLogin());
    }
  }, [dispatch, externalAuthURL]);

  const handleSubmit = (values: LoginValues) => {
    authenticate.mutate({
      body: {
        username: values.username,
        password: values.password,
      },
    });
  };
  return (
    <PageContent>
      <Strip>
        <Row>
          <Col emptyLarge={4} size={6}>
            {authenticationError ? (
              authenticationError === "Session expired" ? (
                <NotificationBanner role="alert" severity="information">
                  Your session has expired. Plese log in again to continue using
                  MAAS.
                </NotificationBanner>
              ) : (
                <NotificationBanner
                  role="alert"
                  severity="negative"
                  title="Error:"
                >
                  {formatErrors(authenticationError, "__all__")}
                </NotificationBanner>
              )
            ) : null}
            {noUsers && !externalAuthURL ? (
              <Card title={Labels.NoUsers}>
                <p>Use the following command to create one:</p>
                <Code copyable>sudo maas createadmin</Code>
                <Button
                  className="u-no-margin--bottom"
                  onClick={() => dispatch(statusActions.checkAuthenticated())}
                >
                  Retry
                </Button>
              </Card>
            ) : (
              <Card>
                <h1 className="p-card__title p-heading--3">Login</h1>
                {externalAuthURL ? (
                  <Button
                    appearance="positive"
                    className="login__external"
                    element="a"
                    href={externalLoginURL}
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    {Labels.ExternalLoginButton}
                  </Button>
                ) : (
                  <FormikForm<LoginValues, LoginError>
                    aria-label={Labels.APILoginForm}
                    initialValues={{
                      password: "",
                      username: "",
                    }}
                    onSubmit={(values) => {
                      if (!hasEnteredUsername) {
                        setSubmittedUsername(values.username);
                      } else {
                        if (isOIDCUser) {
                          // OIDC login - redirect to provider's auth page
                          window.location.href = loginState.oidcURL;
                        } else {
                          // Local login
                          handleSubmit(values);
                        }
                      }
                    }}
                    saved={authenticate.isSuccess}
                    saving={loginState.isPending || authenticate.isPending}
                    submitLabel={
                      !hasEnteredUsername
                        ? "Next"
                        : isOIDCUser
                          ? `Login with ${loginState.providerName}`
                          : Labels.Submit
                    }
                    validationSchema={generateSchema(
                      hasEnteredUsername && !isOIDCUser
                    )}
                  >
                    {isOIDCUser ? (
                      <p>
                        Please sign in with {loginState.providerName} to
                        continue.
                      </p>
                    ) : null}
                    <FormikField
                      aria-hidden={hasEnteredUsername}
                      hidden={hasEnteredUsername}
                      label={hasEnteredUsername ? "" : Labels.Username}
                      name="username"
                      required={true}
                      takeFocus={!hasEnteredUsername}
                      type="text"
                    />
                    <FormikField
                      aria-hidden={!requirePassword}
                      hidden={!requirePassword}
                      label={requirePassword ? Labels.Password : ""}
                      name="password"
                      required={requirePassword}
                      takeFocus={requirePassword}
                      type="password"
                    />
                  </FormikForm>
                )}
              </Card>
            )}
          </Col>
        </Row>
      </Strip>
    </PageContent>
  );
};

export default Login;
