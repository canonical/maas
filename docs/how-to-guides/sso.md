# Single Sign-On

Single Sign-On (SSO) allows users to log in to multiple applications with a single set of credentials. In MAAS, you can configure SSO using an external identity provider (IdP) that supports the OpenID Connect (OIDC) protocol.

This guide explains how to configure SSO using an OIDC-compliant IdP in MAAS.

## Prerequisites

Before you begin, ensure you have completed the following prerequisites:

### Set Up an OIDC-compliant Identity Provider

Ensure your OIDC-compliant IdP is set up and configured. This IdP will handle user authentication and provide the necessary information for MAAS to integrate with it. Register a new application with your IdP for MAAS, and keep the following details handy:

- **Client ID**: The unique identifier for your application registered with the IdP.

- **Client Secret**: The secret key associated with your application.

- **Issuer (IdP) URL**: The URL of your identity provider's authorization server.

- **Expected access token format**: Ensure you know the format of the access tokens issued by your IdP (JWT or opaque) as this will be needed later.

MAAS supports the following IdPs:

- [Auth0](https://auth0.com/)

- [Microsoft Entra ID](https://entra.microsoft.com/)

- [Keycloak](https://keycloak.org/)

Other OIDC-compliant IdPs may also work with MAAS, but are not officially supported or tested.

MAAS provides full UI and CLI authentication support for the providers listed above. For CLI authentication, MAAS performs user validation with the identity provider, which is currently implemented only for Auth0, Microsoft Entra ID, and Keycloak.

When using any other OIDC provider, UI authentication may still work and the CLI can still be used. However, MAAS does not contact the identity provider to verify that the authenticated user exists or is enabled. Managing user status, in these cases, is therefore the responsibility of the identity provider and its configuration.

### Enable TLS in MAAS

The OpenID Connect specification requires that communication between the client (MAAS) and the IdP is secure. Ensure that TLS is enabled in your MAAS deployment. You can configure TLS by following the instructions in [Configuring TLS](https://canonical.com/maas/docs/3.7/how-to-guides/enhance-maas-security/#enable-tls).

### Set up an Admin User

Configuring SSO in MAAS requires administrator privileges. Ensure you have created an admin user before continuing. You can do this by following the instructions in [Creating an admin account](https://canonical.com/maas/docs/3.7/reference/cli-reference/createadmin).

## Setting up a provider in MAAS

In the MAAS Web UI, go to the Single Sign-On configuration page. This can be found in Settings > User Management > OIDC/Single sign-on (`/MAAS/r/settings/user-management/single-sign-on`). Fill out the details for your OIDC provider:

- **Name**: A display name for this provider inside MAAS. This name will appear on the login page so users can select it. It does not need to match any name used in the IdP configuration.

- **Vendor**: The vendor of your IdP. If your IdP is not listed, select "Generic".

- **Client ID**: The Client ID you obtained from your IdP.

- **Client Secret**: The Client Secret you obtained from your IdP.

- **Issuer URL**: The base OpenID Connect issuer URL of your Identity Provider. MAAS uses this URL to discover the IdP’s authentication, token, and user information endpoints automatically (via OIDC discovery).

- **Redirect URI**: This is the MAAS URI that your IdP will redirect to after authentication. Unless you have specific requirements (such as network proxies), this should be set to your MAAS URL followed by `/r/login/oidc/callback`. This exact URI must also be registered in your IdP’s OAuth/OIDC client configuration.

- **Scopes**: A space-separated list of scopes MAAS will request from the IdP. The exact scope names you need will depend on your IdP and its configuration, but in general, MAAS requires the `openid`, `profile`, `email` and `offline_access` scopes to function properly.

- **Token Type**: The expected access token format issued by your IdP.

  - **JWT**: A signed token that MAAS can validate locally.

  - **Opaque**: A token that must be validated by the IdP.

  If unsure, select Opaque or check your IdP documentation.

Once you save the configuration, MAAS will attempt to discover the necessary endpoints from the IdP. If discovery is successful, you are ready to use SSO.


## Setting up Auth0 as an IdP
1. Open an account on [Auth0](https://auth0.com/) and log in to the Auth0 dashboard.
2. After logging in, go to `Applications` > `Applications` from the left-hand menu. Then, click the `Create Application` button.
3. Give your application a name, and select `Regular Web Application` as the application type. Click `Create`.
4. Go to the `Settings` tab of your newly created application. Scroll to the `Application URIs` section and set the `Allowed Callback URLs` to your MAAS URL followed by `/r/login/oidc/callback`. 
    - For example, if your MAAS URL is `https://example.com:5443/MAAS`, set the callback URL to `https://example.com:5443/MAAS/r/login/oidc/callback`.
5. Scroll down to the `Advanced Settings` section, and click on the `Grant Types` tab.
    - Ensure that the `Authorization Code`, `Refresh Token`, and `Client Credentials` grant types are enabled.
6. Select `Save`.
7. Scroll to the top, and go to the `API Access` tab for your application.
    - For the `Auth0 Management API` row, click the `Edit` button.
    - Go to the `Client Access` tab.
    - Search for and select the `read:users` permission. 
    - Click `Grant Access` to save the changes.
8. Auth0 is now ready to be used with MAAS. From the `Settings` tab, copy the `Client ID`, `Client Secret`, and `Domain` (which will be used as the Issuer URL) to configure your provider in MAAS.


## Setting up Microsoft Entra ID as an IdP
1. Create an account and log in to the [Microsoft Entra admin center](https://entra.microsoft.com/).
2. From the left-hand menu, under the `Entra ID` section, select `App registrations` > `New registration`.
3. Give your application a name. For the redirect URI, select `Web` and enter your MAAS URL followed by `/r/login/oidc/callback`. Click `Register`.
4. Note the `Directory (tenant) ID` and `Application (client) ID` from the application overview page.
    - Your issuer URL will be in the format `https://login.microsoftonline.com/<Directory (tenant) ID>/v2.0`.
5. Go to the `Certificates & secrets` tab, and click `New client secret`.
    - Add a description and select an expiration period. Click `Add`.
    - Note the generated client secret value, as it will not be shown again.
6. Go to the `API permissions` tab, and click `Add a permission`.
    - Select `Microsoft Graph` > `Delegated permissions`.
    - Search for and select the following permissions: `openid`, `profile`, `email`, and `offline_access`. Click `Add permissions`.
7. Click `Add a permission` again.
    - Select `Microsoft Graph` > `Application permissions`.
    - Search for and select the following permission: `Directory.Read.All`. Click `Add permissions`.
    - Click `Grant admin consent for Default Directory` to grant the permissions you just added.
8. Entra ID is now ready to be used with MAAS. Use the `Application (client) ID`, `Client Secret`, and the issuer URL you constructed earlier to configure your provider in MAAS.


## Setting up Keycloak as an IdP
1. Ensure keycloak is running and accessible. Log in to the Keycloak admin console.
2. From the left-hand menu, select `Clients` > `Create client`.
    - Enter a Client ID, a name and a description. Then, click `Next`.
    - Enable `Client authentication` and ensure `Standard flow` and `Service account roles` are enabled. Click `Next`.
    - Add the redirect URI for your MAAS instance, which should be your MAAS URL followed by `/r/login/oidc/callback`. Click `Save`.
3. Go to the `Credentials` tab and note the `Secret` value. This will be used as the Client Secret in MAAS.
4. Go to the `Service account roles` tab.
    - Click `Assign role` > `Client roles`.
    - Search for and select the `view-users` role. Click `Assign`.
5. To create a test user, go to the `Users` section in the left-hand menu and click `Add user`.
    - Fill in the required details and click `Create`.
    - Go to the `Credentials` tab for the user and set a password. Ensure that you disable the "Temporary" option so that the user can log in without being forced to change their password.
6. Keycloak is now ready to be used with MAAS. Use the Client ID, Client Secret, and the issuer URL (which is typically in the format `https://<keycloak-domain>/realms/master`, if you are using the master realm) to configure your provider in MAAS.



## Use Single Sign-On

To test the IdP configuration:

1. Log out of MAAS if you are currently logged in.

2. Go to the MAAS login page.

3. Enter a username that exists in your IdP and is not a local MAAS user.

4. Click the "Sign in with [Provider Name]" button that corresponds to the provider you just configured.

5. You will be redirected to your IdP’s login page. Enter the credentials for the user you want to log in as.

6. After successful authentication, you will be redirected back to MAAS and logged in as that user. MAAS will create a new user profile based on the information received from the IdP.

Note that Single Sign-On does not replace local login. Local users will still have access to the regular password-based authentication.


## Tear down

To remove the SSO configuration, simply go back to the Single Sign-On configuration page in the MAAS Web UI and delete the provider you created by clicking the `Reset SSO configuration` button. This will also delete any MAAS users created through that provider. If you wish to disable the provider without deleting it, run:

```shell
maas $PROFILE oidc-provider update <id> enabled=False
```

where `<id>` is the ID of the provider you want to disable.

## Troubleshooting

### Encountering conflict exceptions when creating/updating a provider

This occurs due to two reasons:

1. You are attempting to create or update a provider with a name that is already used by another provider. Provider names must be unique.

2. You are attempting to create or update a provider with `enabled=True`, but another provider is already enabled. MAAS currently supports only one enabled OIDC provider at a time. Ensure you have disabled the currently enabled provider before enabling another one.

### Deleting an enabled provider from the API/CLI

When attempting to delete a provider using the REST API or CLI, you may encounter the error message: "Provider is currently enabled and cannot be deleted."

Ensure you disable the provider before deleting it.

### Encountering post-login redirect errors

After signing in at your IdP, you may sometimes encounter redirect errors depending on your IdP configuration. Common causes include:

1. Your provider configuration restricts logins to specific email domains, but the account you used belongs to a different domain.

2. The **Redirect URI** in your MAAS provider configuration does not exactly match the URI registered in your IdP, causing the IdP to reject the authentication response.

3. The IdP is not configured to allow the scopes requested by MAAS (for example `openid`, `profile`, `email`, or `offline_access`), so the authentication response is rejected.
