Enter keyword arguments in the form `key=value`.

## Abort a node operation

```bash
maas $PROFILE rack-controller abort [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Abort a node's current operation.

#### Keyword "comment"
Optional String. Comment for the event log.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Delete a rack controller

```bash
maas $PROFILE rack-controller delete [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Deletes a rack controller with the given system_id. A rack controller cannot be deleted if it is set to `primary_rack` on a `VLAN` and another rack controller cannot be used to provide DHCP for said VLAN. Use `force` to override this behavior.

Using `force` will also allow deleting a rack controller that is hosting pod virtual machines. The pod will also be deleted.

Rack controllers that are also region controllers will be converted to a region controller (and hosted pods will not be affected).

#### Keyword "force"
Optional Boolean.  Always delete the rack controller even if it is the `primary_rack` on a `VLAN` and another rack controller cannot provide DHCP on that VLAN. This will disable DHCP on those VLANs.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Get system details

```bash
maas $PROFILE rack-controller details [--help] [-d] [-k] system_id [data ...]
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

## Import boot images

```bash
maas $PROFILE rack-controller import-boot-images [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Import boot images on a given rack controller or all rack controllers. (deprecated)

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## List available boot images

```bash
maas $PROFILE rack-controller list-boot-images [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Lists all available boot images for a given rack controller system_id and whether they are in sync with the region controller. (deprecated)

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Ignore failed tests

```bash
maas $PROFILE rack-controller override-failed-testing [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Ignore failed tests and put node back into a usable state.

#### Keyword "comment"
Optional String. Comment for the event log.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Power off a node

```bash
maas $PROFILE rack-controller power-off [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Powers off a given node.

#### Keyword "stop_mode"
Optional String.  Power-off mode. If 'soft', perform a soft power down if the node's power type supports it, otherwise perform a hard power off. For all values other than 'soft', and by default, perform a hard power off. A soft power off generally asks the OS to shutdown the system gracefully before powering off, while a hard power off occurs immediately without any warning to the OS.

#### Keyword "comment"
Optional String. Comment for the event log.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Turn on a node

```bash
maas $PROFILE rack-controller power-on [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Turn on the given node with optional user-data and comment.

#### Keyword "user_data"
Optional String. Base64-encoded blob of data to be made available to the nodes through the metadata service.

#### Keyword "comment"
Optional String. Comment for the event log.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Get power parameters

```bash
maas $PROFILE rack-controller power-parameters [--help] [-d] [-k] system_id [data ...]
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

## Get the power state of a node

```bash
maas $PROFILE rack-controller query-power-state [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Gets the power state of a given node. MAAS sends a request to the node's power controller, which asks it about the node's state. The reply to this could be delayed by up to 30 seconds while waiting for the power controller to respond.  Use this method sparingly as it ties up an appserver thread while waiting.

#### Keyword "system_id"
Required String. The node to query.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Read a node

```bash
maas $PROFILE rack-controller read [--help] [-d] [-k] system_id [data ...]
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

## Begin testing process for a node

```bash
maas $PROFILE rack-controller test [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Begins the testing process for a given node.

A node in the 'ready', 'allocated', 'deployed', 'broken', or any failed state may run tests. If testing is started and successfully passes from 'broken' or any failed state besides 'failed commissioning' the node will be returned to a ready state. Otherwise the node will return to the state it was when testing started.

#### Keyword "enable_ssh"
Optional Int.  Whether to enable SSH for the testing environment using the user's SSH key(s). 0 == false. 1 == true.

#### Keyword "testing_scripts"
Optional String.  A comma-separated list of testing script names and tags to be run. By default all tests tagged 'commissioning' will be run. 

#### Keyword "parameters"
Optional String.  Scripts selected to run may define their own parameters. These parameters may be passed using the parameter name. Optionally a parameter may have the script name prepended to have that parameter only apply to that specific script.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Update a rack controller

```bash
maas $PROFILE rack-controller update [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Updates a rack controller with the given system_id.

#### Keyword "description"
Optional String. The new description for this given rack controller.

#### Keyword "power_type"
Optional String.  The new power type for the given rack controller. If you use the default value, power_parameters will be set to an empty string. See the `Power types`_ section for a list of available power types. Note that only admin users can set this parameter.

#### Keyword "power_parameters_skip_check"
Optional Boolean.  If true, the new power parameters for the given rack controller will be checked against the expected parameters for the rack controller's power type. Default is false.

#### Keyword "zone"
Optional String. The name of a valid zone in which to place the given rack controller.

#### Keyword "domain"
Optional String. The domain for this controller. If not given the default domain is used.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Import boot images

```bash
maas $PROFILE rack-controller import-boot-images [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Import boot images on a given rack controller or all rack controllers. (deprecated)

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## MAC address registered

```bash
maas $PROFILE rack-controllers is-registered [--help] [-d] [-k] [data ...]
```

Returns whether or not the given MAC address is registered within this MAAS (and attached to a non-retired node).

#### Keyword "mac_address"
Required URL String. The MAC address to be checked.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Get power parameters

```bash
maas $PROFILE rack-controllers power-parameters [--help] [-d] [-k] [data ...]
```

Get power parameters for multiple machines. To request power parameters for a specific machine or more than one machine:

``op=power_parameters&id=abc123&id=def456``.

#### Keyword "id"
Required URL String.  A system ID. To request more than one machine, provide multiple ``id`` arguments in the request. Only machines with matching system ids will be returned.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## List Nodes visible to the user

```bash
maas $PROFILE rack-controllers read [--help] [-d] [-k] [data ...] 
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
Optional String.  Only return nodes which have one or more devices containing the following constraints in the `format key=value[,key2=value2[,...]]`.

Each key can be one of the following:

- ``vendor_id``: The device vendor id
- ``product_id``: The device product id
- ``vendor_name``: The device vendor name, not case sensative
- ``product_name``: The device product name, not case sensative
- ``commissioning_driver``: The device uses this driver during commissioning.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Assign nodes to a zone

```bash
maas $PROFILE rack-controllers set-zone [--help] [-d] [-k] [data ...] 
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

