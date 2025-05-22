Enter keyword arguments in the form `key=value`.

## Read commissioning results

```bash
maas $PROFILE node-results read [--help] [-d] [-k] [data ...] 
```

Read the commissioning results per node visible to the user, optionally filtered.

#### Keyword "system_id"
Optional String. An optional list of system ids. Only the results related to the nodes with these system ids will be returned.

#### Keyword "name"
Optional String. An optional list of names. Only the results with the specified names will be returned.

#### Keyword "result_type"
Optional String. An optional result_type. Only the results with the specified result_type will be returned.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

