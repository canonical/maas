Enter keyword arguments in the form `key=value`.

## Deletes a VM cluster

```bash
maas $PROFILE vm-cluster delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Deletes a VM cluster with the given ID.

#### Keyword "decompose"
Optional Boolean. Whether to also decompose all machines in the VM cluster on removal. If not provided, machines will not be removed.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit|
| -d, --debug    | Display more information about API responses|
| -k, --insecure | Disable SSL certificate check                 |

## This operation has been deprecated in favor of 'Virtual-machine-host read'.

```bash
maas $PROFILE vm-cluster read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit|
| -d, --debug    | Display more information about API responses|
| -k, --insecure | Disable SSL certificate check                 |

## Update a VM cluster

```bash
maas $PROFILE vm-cluster update [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Update a specific VM cluster by ID.

#### Keyword "name"
Optional String. The VM cluster's name.

#### Keyword "pool"
Optional String. The name of the resource pool associated with this VM Cluster -- this change is propagated to VM hosts

#### Keyword "zone"
Optional String. The VM cluster's zone.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit|
| -d, --debug    | Display more information about API responses|
| -k, --insecure | Disable SSL certificate check                 |

