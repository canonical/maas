Configure HashiCorp Vault for use with MAAS.

```bash
maas config-vault configure [-h] [--mount MOUNT] [--yes] url role_id wrapped_token secrets_path
```

```bash
maas config-vault migrate [-h] 
```

```bash
maas config-vault status [-h] 
```

#### Positional arguments
| Argument      | Effect                                           |
|---------------|--------------------------------------------------|
| url           | Vault URL                                        |
| role_id       | Vault AppRole Role ID                            |
| wrapped_token | Vault wrapped token for the AppRole secret_id    |
| secrets_path  | Path prefix for MAAS secrets in Vault KV storage |

#### Command-line options
| Option        | Effect                                         |
|---------------|------------------------------------------------|
| -h, --help    | show this help message and exit                |
| --mount MOUNT | Vault KV mount path (default: secret)          |
| --yes         | Skip interactive confirmation (default: False) |

