Enter keyword arguments in the form `key=value`.

## Delete a region controller

```bash
maas $PROFILE region-controller delete [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Deletes a region controller with the given system_id.

A region controller cannot be deleted if it hosts pod virtual machines. Use `force` to override this behavior. Forcing deletion will also remove hosted pods.

#### Keyword "force"
Optional Boolean. Tells MAAS to override disallowing deletion of region controllers that host pod virtual machines.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Get system details

```bash
maas $PROFILE region-controller details [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Returns system details -- for example, LLDP and ``lshw`` XML dumps.

Returns a ``{detail_type: xml, ...}`` map, where ``detail_type`` is something like "lldp" or "lshw".

Note that this is returned as BSON and not JSON. This is for efficiency, but mainly because JSON can't do binary content without applying additional encoding like base-64. The example output below is represented in ASCII using ``bsondump example.bson`` and is for demonstrative purposes.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Get power parameters

```bash
maas $PROFILE region-controller power-parameters [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Gets power parameters for a given system_id, if any. For some types of power control this will include private information such as passwords and secret keys.

Note that this method is reserved for admin users and returns a 403 if the user is not one.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Read a node

```bash
maas $PROFILE region-controller read [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Reads a node with the given system_id.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Update a region controller

```bash
maas $PROFILE region-controller update [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Updates a region controller with the given system_id.

#### Keyword "description"
Optional String. The new description for this given region controller.

#### Keyword "power_type"
Optional String.  The new power type for this region controller. If you use the default value, power_parameters will be set to the empty string.  Available to admin users.  See the `Power types`_ section for a list of the available power types.

#### Keyword "power_parameters_skip_check"
Optional String.  Whether or not the new power parameters for this region controller should be checked against the expected power parameters for the region controller's power type ('true' or 'false').  The default is 'false'. 

#### Keyword "zone"
Optional String. Name of a valid physical zone in which to place this region controller.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Read a node

```bash
maas $PROFILE region-controller read [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Reads a node with the given system_id.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Assign nodes to a zone

```bash
maas $PROFILE region-controllers set-zone [--help] [-d] [-k] [data ...] 
```

Assigns a given node to a given zone.

#### Keyword "zone"
Required String. The zone name.

#### Keyword "nodes"
Required String. The node to add.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |
