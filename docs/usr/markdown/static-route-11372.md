Enter keyword arguments in the form `key=value`.

## Delete static route

```bash
maas $PROFILE static-route delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Deletes the static route with the given ID.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Get a static route

```bash
maas $PROFILE static-route read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Gets a static route with the given ID.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Update a static route

```bash
maas $PROFILE static-route update [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Updates a static route with the given ID.

#### Keyword "source"
Optional String. Source subnet name for the route.

#### Keyword "destination"
Optional String. Destination subnet name for the route.

#### Keyword "gateway_ip"
Optional String.  IP address of the gateway on the source subnet.

#### Keyword "metric"
Optional Int. Weight of the route on a deployed machine.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Create a static route

```bash
maas $PROFILE static-routes create [--help] [-d] [-k] [data ...] 
```

Creates a static route.

#### Keyword "source"
Required String. Source subnet name for the route.

#### Keyword "destination"
Required String. Destination subnet name for the route.

#### Keyword "gateway_ip"
Required String.  IP address of the gateway on the source subnet.

#### Keyword "metric"
Optional Int. Weight of the route on a deployed machine.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## List static routes

```bash
maas $PROFILE static-routes read [--help] [-d] [-k] [data ...] 
```

Lists all static routes. 

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

