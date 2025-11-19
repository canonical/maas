Configure MAAS Region Vault integration.

```bash
maas config-vault [-h] COMMAND ...

```


#### **Command-line options**
| Option | Effect |
|---|---|
| -h, --help | show this help message and exit. |




#### **Drill down**
| Command | Effect |
|---|---|
| configure | Update MAAS configuration to use Vault secret storage. |
| migrate | Migrate secrets to Vault |
| status | Report status of Vault integration |





```bash
maas config-vault configure [-h] [--mount MOUNT] [--yes]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| url | The url parameter |
| role_id | The role_id parameter |
| wrapped_token | The wrapped_token parameter |
| secrets_path | The secrets_path parameter |


#### **Command-line options**
| Option | Effect |
|---|---|
| -h, --help | show this help message and exit. |
| --mount | Vault KV mount path. |
| --yes | Skip interactive confirmation. |







```bash
maas config-vault migrate [-h]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| -h, --help | show this help message and exit. |







```bash
maas config-vault status [-h]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| -h, --help | show this help message and exit. |
