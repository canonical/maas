Single Sign-On (SSO) allows users to log in to multiple applications with a single set of credentials. In MAAS, you can configure SSO using an external identity provider (IdP) that supports the OpenID Connect (OIDC) protocol.

This guide explains how to configure SSO using an OIDC-compliant IdP in MAAS 3.8 and later versions.

## Prerequisites

Before you begin, ensure you have completed the following prerequisites:

### Set Up an OIDC-compliant Identity Provider

Ensure your OIDC-compliant IdP is set up and configured. This IdP will handle user authentication and provide the necessary information for MAAS to integrate with it. Register a new application with your IdP for MAAS, and keep the following details handy:

- **Client ID**: The unique identifier for your application registered with the IdP.

- **Client Secret**: The secret key associated with your application.

- **Issuer (IdP) URL**: The URL of your identity provider's authorization server.

- **Expected access token format**: Ensure you know the format of the access tokens issued by your IdP (JWT or opaque) as this will be needed later.

Some examples of OIDC-compliant IdPs include:

- [Canonical Identity Platform](https://canonical-identity.readthedocs-hosted.com/)

- [Auth0](https://auth0.com/)

- [Okta](https://okta.com/)

- [Keycloak](https://keycloak.org/)

### Enable TLS in MAAS

The OpenID Connect specification requires that communication between the client (MAAS) and the IdP is secure. Ensure that TLS is enabled in your MAAS deployment. You can configure TLS by following the instructions in [Configuring TLS](https://discourse.maas.io/t/how-to-enhance-maas-security/5196#p-9102-configure-tls-33-2).

### Set up an Admin User

Configuring SSO in MAAS requires administrator privileges. Ensure you have created an admin user before continuing. You can do this by following the instructions in [Creating an admin account](https://discourse.maas.io/t/createadmin/11379).

## Setting up a provider in MAAS

In the MAAS Web UI, go to the Single Sign-On configuration page. This can be found in Settings > User Management > OIDC/Single sign-on (`/MAAS/r/settings/user-management/single-sign-on`). Fill out the details for your OIDC provider:

- **Name**: A display name for this provider inside MAAS. This name will appear on the login page so users can select it. It does not need to match any name used in the IdP configuration.

- **Client ID**: The Client ID you obtained from your IdP.

- **Client Secret**: The Client Secret you obtained from your IdP.

- **Issuer URL**: The base OpenID Connect issuer URL of your Identity Provider. MAAS uses this URL to discover the IdP’s authentication, token, and user information endpoints automatically (via OIDC discovery).

- **Redirect URI**: This is the URL that your IdP will redirect to after authentication. Unless you have specific requirements (such as network proxies), this should be set to your MAAS URL followed by `/r/login/oidc/callback`. This exact URI must also be registered in your IdP’s OAuth/OIDC client configuration.

- **Scopes**: A space-separated list of scopes MAAS will request from the IdP. The exact scope names you need will depend on your IdP and its configuration, but in general, MAAS requires the `openid`, `profile`, `email` and `offline_access` scopes to function properly.

- **Token Type**: The expected access token format issued by your IdP.

  - **JWT**: A signed token that MAAS can validate locally.

  - **Opaque**: A token that must be validated by the IdP.

  If unsure, select Opaque or check your IdP documentation.

Once you save the configuration, MAAS will attempt to discover the necessary endpoints from the IdP. If discovery is successful, you are ready to use SSO.

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

To remove the SSO configuration, simply go back to the Single Sign-On configuration page in the MAAS Web UI and delete the provider you created by clicking the "Reset SSO configuration" button. This will also delete any MAAS users created through that provider. If you wish to disable the provider without deleting it, run:

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