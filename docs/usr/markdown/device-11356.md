Enter keyword arguments in the form `key=value`.

## Delete a device

```bash
maas $PROFILE device delete [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id

Delete a device with the given system_id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Get system details

```bash
maas $PROFILE device details [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id

Returns system details -- for example, LLDP and ``lshw`` XML dumps.

Returns a ``{detail_type: xml, ...}`` map, where ``detail_type`` is something like "lldp" or "lshw".

Note that this is returned as BSON and not JSON. This is for efficiency, but mainly because JSON can't do binary content without applying additional encoding like base-64. The example output below is represented in ASCII using ``bsondump example.bson`` and is for demonstrative purposes.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Get power parameters

```bash
maas $PROFILE device power-parameters [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Gets power parameters for a given system_id, if any. For some types of power control this will include private information such as passwords and secret keys.

Note that this method is reserved for admin users and returns a 403 if the user is not one.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a node

```bash
maas $PROFILE device read [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id

Reads a node with the given system_id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Reset device configuration

```bash
maas $PROFILE device restore-default-configuration [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Restore the configuration options of a device with the given system_id to default values.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Reset networking options

```bash
maas $PROFILE device restore-networking-configuration [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Restore the networking options of a device with the given system_id to default values.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Deprecated, use set-workload-annotations.

```bash
maas $PROFILE device set-owner-data [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Deprecated, use set-workload-annotations instead.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Set key=value data

```bash
maas $PROFILE device set-workload-annotations [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Set `key=value` data for the current owner.

Pass any `key=value` form data to this method to add, modify, or remove. A key is removed when the value for that key is set to an empty string.

This operation will not remove any previous keys unless explicitly passed with an empty string. All workload annotations are removed when the machine is no longer allocated to a user.

#### Keyword "key"
Required String. ``key`` can be any string value.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a device

```bash
maas $PROFILE device update [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id


Update a device with a given system_id.

#### Keyword "hostname"
Optional String. The hostname for this device.

#### Keyword "description"
Optional String. The optional description for this machine.

#### Keyword "domain"
Optional String. The domain for this device.

#### Keyword "parent"
Optional String.  Optional `system_id` to indicate this device's parent. If the parent is already set and this parameter is omitted, the parent will be unchanged.

#### Keyword "zone"
Optional String. Name of a valid physical zone in which to place this node.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## MAC address registered

```bash
maas $PROFILE devices is-registered [--help] [-d] [-k] [data ...] 
```

Returns whether or not the given MAC address is registered within this MAAS (and attached to a non-retired node).

#### Keyword "mac_address"
Required URL String. The MAC address to be checked.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List Nodes visible to the user

```bash
maas $PROFILE devices read [--help] [-d] [-k] [data ...] 
```

List nodes visible to current user, optionally filtered by criteria.

Nodes are sorted by id (i.e. most recent last) and grouped by type.

#### Keyword "hostname"
Optional String.  Only nodes relating to the node with the matching hostname will be returned. This can be specified multiple times to see multiple nodes.

#### Keyword "cpu_count"
Optional Int. Only nodes with the specified minimum number of CPUs will be included.

#### Keyword "mem"
Optional String. Only nodes with the specified minimum amount of RAM (in MiB) will be included.

#### Keyword "mac_address"
Optional String.  Only nodes relating to the node owning the specified MAC address will be returned. This can be specified multiple times to see multiple nodes.

#### Keyword "id"
Optional String. Only nodes relating to the nodes with matching system ids will be returned.

#### Keyword "domain"
Optional String. Only nodes relating to the nodes in the domain will be returned.

#### Keyword "zone"
Optional String. Only nodes relating to the nodes in the zone will be returned.

#### Keyword "pool"
Optional String. Only nodes belonging to the pool will be returned.

#### Keyword "agent_name"
Optional String. Only nodes relating to the nodes with matching agent names will be returned.

#### Keyword "fabrics"
Optional String. Only nodes with interfaces in specified fabrics will be returned.

#### Keyword "not_fabrics"
Optional String. Only nodes with interfaces not in specified fabrics will be returned.

#### Keyword "vlans"
Optional String. Only nodes with interfaces in specified VLANs will be returned.

#### Keyword "not_vlans"
Optional String. Only nodes with interfaces not in specified VLANs will be returned.

#### Keyword "subnets"
Optional String. Only nodes with interfaces in specified subnets will be returned.

#### Keyword "not_subnets"
Optional String. Only nodes with interfaces not in specified subnets will be returned.

#### Keyword "link_speed"
Optional String.  Only nodes with interfaces with link speeds greater than or equal to link_speed will be returned.

#### Keyword "status"
Optional String. Only nodes with specified status will be returned.

#### Keyword "pod"
Optional String. Only nodes that belong to a specified pod will be returned.

#### Keyword "not_pod"
Optional String. Only nodes that don't belong to a specified pod will be returned.

#### Keyword "pod_type"
Optional String. Only nodes that belong to a pod of the specified type will be returned.

#### Keyword "not_pod_type"
Optional String. Only nodes that don't belong a pod of the specified type will be returned.

#### Keyword "devices"
Optional String.  Only return nodes which have one or more devices containing the following constraints in the format `key=value[,key2=value2[,...]]`.

Each key can be one of the following:

- ``vendor_id``: The device vendor id
- ``product_id``: The device product id
- ``vendor_name``: The device vendor name, not case sensative
- ``product_name``: The device product name, not case sensative
- ``commissioning_driver``: The device uses this driver during commissioning.
Type: String.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Assign nodes to a zone

```bash
maas $PROFILE devices set-zone [--help] [-d] [-k] [data ...] 
```

Assigns a given node to a given zone.

#### Keyword "zone"
Required String. The zone name.

#### Keyword "nodes"
Required String. The node to add.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

