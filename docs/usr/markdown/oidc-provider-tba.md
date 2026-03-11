Delete OIDC provider

```bash
maas $PROFILE oidc-provider delete [--help] [-d] [-k] id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Delete an OIDC provider by ID.





Get OIDC provider

```bash
maas $PROFILE oidc-provider read [--help] [-d] [-k] id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Retrieve an OIDC provider by ID.





Update OIDC provider

```bash
maas $PROFILE oidc-provider update [--help] [-d] [-k] id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Update an existing OIDC provider by ID.

##### Keyword "name"
Optional String. New name for the OIDC provider.
##### Keyword "issuer_url"
Optional String. New issuer URL for the OIDC provider.
##### Keyword "client_id"
Optional String. New client ID for the OIDC provider.
##### Keyword "client_secret"
Optional String. New client secret for the OIDC provider.
##### Keyword "enabled"
Optional Boolean. Whether the OIDC provider should be enabled.
##### Keyword "token_type"
Optional String. New token type for the OIDC provider (JWT or Opaque).
##### Keyword "redirect_uri"
Optional String. New redirect URI for the OIDC provider.
##### Keyword "scopes"
Optional String. Space-separated list of scopes for the OIDC provider.


Note: This command accepts JSON.


Create OIDC provider

```bash
maas $PROFILE oidc-providers create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a new OIDC provider.

##### Keyword "name"
Optional String. Name for the new OIDC provider.
##### Keyword "issuer_url"
Optional String. Issuer URL for the new OIDC provider.
##### Keyword "client_id"
Optional String. Client ID for the new OIDC provider.
##### Keyword "client_secret"
Optional String. Client secret for the new OIDC provider.
##### Keyword "enabled"
Optional Boolean. Whether the OIDC provider is enabled. Defaults to false.
##### Keyword "token_type"
Optional String. Token type for the OIDC provider (JWT or Opaque). Defaults to JWT.
##### Keyword "redirect_uri"
Optional String. Redirect URI for the OIDC provider.
##### Keyword "scopes"
Optional String. Space-separated list of scopes for the OIDC provider.


Note: This command accepts JSON.


Get active OIDC provider

```bash
maas $PROFILE oidc-providers get-active [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Get the currently enabled OIDC provider.





List OIDC providers

```bash
maas $PROFILE oidc-providers read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all configured OIDC providers.
