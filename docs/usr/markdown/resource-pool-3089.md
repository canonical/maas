Enter keyword arguments in the form `key=value`.

## Deletes a resource pool.

```bash
maas $PROFILE resource-pool delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Returns a resource pool.

```bash
maas $PROFILE resource-pool read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Updates a resource pool's name or description.

```bash
maas $PROFILE resource-pool update [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Note that any other given parameters are silently ignored.

#### Keyword "description"
Optional String. A brief description of the resource pool.

#### Keyword "name"
Optional String. The resource pool's new name.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Creates a new resource pool.

```bash
maas $PROFILE resource-pools create [--help] [-d] [-k] [data ...] 
```

#### Keyword "name" Required.  The new resource pool's name.
Type: String.

#### Keyword "description"
Optional String. A brief description of the new resource pool.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Get a listing of all resource pools.

```bash
maas $PROFILE resource-pools read [--help] [-d] [-k] [data ...] 
```

Note that there is always at least one resource pool: default. 

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

