View or change controller configuration.

```bash
maas config [-h] [--show] [--show-database-password] [--show-secret] \
[--maas-url MAAS_URL] [--vault-uri VAULT_URI] \
[--vault-approle-id VAULT_APPROLE_ID] [--vault-wrapped-token VAULT_WRAPPED_TOKEN] \
[--vault-secrets-path VAULT_SECRETS_PATH]  [--vault-secrets-mount VAULT_SECRETS_MOUNT] \
[--secret SECRET] [--num-workers NUM_WORKERS]  [--enable-debug] [--disable-debug] \
[--enable-debug-queries] [--disable-debug-queries] [--parsable]
```

#### Command-line options
| Option                                    | Effect                                                 |
|-------------------------------------------|--------------------------------------------------------|
| -h, --help                                | show this help message and exit                        |
| --show                                    | Show the current configuration. Default when no        |
|                                           | parameters are provided.                               |
| --show-database-password                  | Show the hidden database password.                     |
| --show-secret                             | Show the hidden secret.                                |
| --maas-url MAAS_URL                       | URL that MAAS should use for communicate from the      |
|                                           | nodes to MAAS and other controllers of MAAS.           |
| --vault-uri VAULT_URI                     | Vault URI                                              |
| --vault-approle-id VAULT_APPROLE_ID       | Vault AppRole Role ID                                  |
| --vault-wrapped-token VAULT_WRAPPED_TOKEN | Vault Wrapped Token for AppRole ID                     |
| --vault-secrets-path VAULT_SECRETS_PATH   | Path prefix for MAAS secrets in Vault KV storage       |
| --vault-secrets-mount VAULT_SECRETS_MOUNT | Vault KV mount path                                    |
| --secret SECRET                           | Secret token required for the rack controller to talk  |
|                                           | to the region controller(s). Only used when in 'rack'  |
|                                           | mode.                                                  |
| --num-workers NUM_WORKERS                 | Number of regiond worker processes to run.             |
| --enable-debug                            | Enable debug mode for detailed error and log           |
|                                           | reporting.                                             |
| --disable-debug                           | Disable debug mode.                                    |
| --enable-debug-queries                    | Enable query debugging. Reports number of queries and  |
|                                           | time for all actions performed. Requires debug to also |
|                                           | be True. mode for detailed error and log reporting.    |
| --disable-debug-queries                   | Disable query debugging.                               |
| --parsable                                | Output the current configuration in a parsable format. |

