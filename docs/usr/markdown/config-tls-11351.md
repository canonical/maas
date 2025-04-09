Enable or disable TLS for MAAS.


```bash
maas config-tls enable [-h] [--cacert CACERT] [-p PORT] [--yes] key cert
```

```bash
maas config-tls disable [-h] 
```

#### Positional arguments
| Argument | Effect                            |
|----------|-----------------------------------|
| key      | path to the private key           |
| cert     | path to certificate in PEM format |

#### Command-line options
| Option               | Effect                                                |
|----------------------|-------------------------------------------------------|
| -h, --help           | show this help message and exit                       |
| --cacert CACERT      | path to CA certificates chain in PEM format (default: |
|                      | None)                                                 |
| -p PORT, --port PORT | HTTPS port (default: 5443)                            |
| --yes                | Skip interactive confirmation (default: False)        |
|                      |                                                       |
