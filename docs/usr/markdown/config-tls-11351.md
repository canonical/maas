Configure MAAS Region TLS.

```bash
maas config-tls [-h] COMMAND ...

```


#### **Command-line options**
| Option | Effect |
|---|---|
| -h, --help | show this help message and exit. |




#### **Drill down**
| Command | Effect |
|---|---|
| enable | Enable TLS and switch to a secured mode (https). |
| disable | Disable TLS and switch to a non-secured mode (http). |





```bash
maas config-tls disable [-h]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| -h, --help | show this help message and exit. |







```bash
maas config-tls enable [-h] [--cacert CACERT] [-p PORT] [--yes]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| key | The key parameter |
| cert | The cert parameter |


#### **Command-line options**
| Option | Effect |
|---|---|
| -h, --help | show this help message and exit. |
| --cacert | path to CA certificates chain in PEM format. |
| -p, --port | HTTPS port. |
| --yes | Skip interactive confirmation. |
