Abort a node operation

```bash
maas $PROFILE rack-controller abort [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Abort a node's current operation.

##### Keyword "comment"
Optional String. Comment for the event log.


Note: This command accepts JSON.


Delete a rack controller

```bash
maas $PROFILE rack-controller delete [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Deletes a rack controller with the given system_id. A<br>rack controller cannot be deleted if it is set to `primary_rack` on<br>a `VLAN` and another rack controller cannot be used to provide DHCP<br>for said VLAN. Use `force` to override this behavior. Using `force` will also allow deleting a rack controller that is<br>hosting pod virtual machines. The pod will also be deleted. Rack controllers that are also region controllers will be converted<br>to a region controller (and hosted pods will not be affected).

##### Keyword "force"
Optional Boolean. Always delete the rack<br>controller even if it is the `primary_rack` on a `VLAN` and another<br>rack controller cannot provide DHCP on that VLAN. This will disable<br>DHCP on those VLANs.


Note: This command accepts JSON.


Get system details

```bash
maas $PROFILE rack-controller details [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Returns system details -- for example, LLDP and<br>``lshw`` XML dumps. Returns a ``{detail_type: xml, …}`` map, where<br>``detail_type`` is something like "lldp" or "lshw". Note that this is returned as BSON and not JSON. This is for<br>efficiency, but mainly because JSON can't do binary content without<br>applying additional encoding like base-64. The example output below is<br>represented in ASCII using ``bsondump example.bson`` and is for<br>demonstrative purposes.





Import boot images

```bash
maas $PROFILE rack-controller import-boot-images [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Import boot images on a given rack controller or all<br>rack controllers. (deprecated)





List available boot images

```bash
maas $PROFILE rack-controller list-boot-images [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Lists all available boot images for a given rack<br>controller system_id and whether they are in sync with the<br>region controller. (deprecated)





Ignore failed tests

```bash
maas $PROFILE rack-controller override-failed-testing [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Ignore failed tests and put node back into a usable state.

##### Keyword "comment"
Optional String. Comment for the event log.


Note: This command accepts JSON.


Power off a node

```bash
maas $PROFILE rack-controller power-off [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Powers off a given node.

##### Keyword "stop_mode"
Optional String. Power-off mode. If 'soft',<br>perform a soft power down if the node's power type supports it,<br>otherwise perform a hard power off. For all values other than 'soft',<br>and by default, perform a hard power off. A soft power off generally<br>asks the OS to shutdown the system gracefully before powering off,<br>while a hard power off occurs immediately without any warning to the<br>OS.
##### Keyword "comment"
Optional String. Comment for the event log.


Note: This command accepts JSON.


Turn on a node

```bash
maas $PROFILE rack-controller power-on [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Turn on the given node with optional user-data and<br>comment.

##### Keyword "user_data"
Optional String. Base64-encoded blob of<br>data to be made available to the nodes through the metadata service.
##### Keyword "comment"
Optional String. Comment for the event log.


Note: This command accepts JSON.


Get power parameters

```bash
maas $PROFILE rack-controller power-parameters [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Gets power parameters for a given system_id, if any. For<br>some types of power control this will include private information such<br>as passwords and secret keys. Note that this method is reserved for admin users and returns a 403 if<br>the user is not one.





Get the power state of a node

```bash
maas $PROFILE rack-controller query-power-state [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Gets the power state of a given node. MAAS sends a request<br>to the node's power controller, which asks it about the node's state.<br>The reply to this could be delayed by up to 30 seconds while waiting<br>for the power controller to respond. Use this method sparingly as it<br>ties up an appserver thread while waiting.

##### Keyword "system_id"
Optional String. The node to query.


Note: This command accepts JSON.


Read a node

```bash
maas $PROFILE rack-controller read [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Reads a node with the given system_id.





Begin testing process for a node

```bash
maas $PROFILE rack-controller test [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Begins the testing process for a given node. A node in the 'ready', 'allocated', 'deployed', 'broken', or any failed<br>state may run tests. If testing is started and successfully passes from<br>'broken' or any failed state besides 'failed commissioning' the node<br>will be returned to a ready state. Otherwise the node will return to<br>the state it was when testing started.

##### Keyword "enable_ssh"
Optional Int. Whether to enable SSH for<br>the testing environment using the user's SSH key(s). 0 == false. 1 ==<br>true.
##### Keyword "testing_scripts"
Optional String. A comma-separated<br>list of testing script names and tags to be run. By default all tests<br>tagged 'commissioning' will be run.
##### Keyword "parameters"
Optional String. Scripts selected to run<br>may define their own parameters. These parameters may be passed using<br>the parameter name. Optionally a parameter may have the script name<br>prepended to have that parameter only apply to that specific script.


Note: This command accepts JSON.


Update a rack controller

```bash
maas $PROFILE rack-controller update [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Updates a rack controller with the given system_id.

##### Keyword "description"
Optional String. The new description for<br>this given rack controller.
##### Keyword "power_type"
Optional String. The new power type for<br>the given rack controller. If you use the default value,<br>power_parameters will be set to an empty string. See the<br>`Power types`_ section for a list of available power types. Note that<br>only admin users can set this parameter.
##### Keyword "power_parameters_skip_check"
Optional Boolean. If<br>true, the new power parameters for the given rack controller will be<br>checked against the expected parameters for the rack controller's power<br>type. Default is false.
##### Keyword "zone"
Optional String. The name of a valid zone in<br>which to place the given rack controller.
##### Keyword "domain"
Optional String. The domain for this<br>controller. If not given the default domain is used.


Note: This command accepts JSON.


Get power information from rack controllers

```bash
maas $PROFILE rack-controllers describe-power-types [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Queries all rack controllers for power information.





Import boot images on all rack controllers

```bash
maas $PROFILE rack-controllers import-boot-images [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Imports boot images on all rack controllers. (deprecated)





MAC address registered

```bash
maas $PROFILE rack-controllers is-registered [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Returns whether or not the given MAC address is registered<br>within this MAAS (and attached to a non-retired node).

##### Keyword "mac_address"
Optional URL String. The MAC address to be<br>checked.


Note: This command accepts JSON.


Get power parameters

```bash
maas $PROFILE rack-controllers power-parameters [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Get power parameters for multiple machines. To request<br>power parameters for a specific machine or more than one machine:<br>``op=power_parameters&id=abc123&id=def456``.

##### Keyword "id"
Optional URL String. A system ID. To request more<br>than one machine, provide multiple ``id`` arguments in the request.<br>Only machines with matching system ids will be returned.


Note: This command accepts JSON.


List Nodes visible to the user

```bash
maas $PROFILE rack-controllers read [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List nodes visible to current user, optionally filtered by<br>criteria. Nodes are sorted by id (i.e. most recent last) and grouped by type.

##### Keyword "hostname"
Optional String. Only nodes relating to the<br>node with the matching hostname will be returned. This can be specified<br>multiple times to see multiple nodes.
##### Keyword "cpu_count"
Optional Int. Only nodes with the specified<br>minimum number of CPUs will be included.
##### Keyword "mem"
Optional String. Only nodes with the specified<br>minimum amount of RAM (in MiB) will be included.
##### Keyword "mac_address"
Optional String. Only nodes relating to<br>the node owning the specified MAC address will be returned. This can be<br>specified multiple times to see multiple nodes.
##### Keyword "id"
Optional String. Only nodes relating to the nodes<br>with matching system ids will be returned.
##### Keyword "domain"
Optional String. Only nodes relating to the<br>nodes in the domain will be returned.
##### Keyword "zone"
Optional String. Only nodes relating to the<br>nodes in the zone will be returned.
##### Keyword "pool"
Optional String. Only nodes belonging to the<br>pool will be returned.
##### Keyword "agent_name"
Optional String. Only nodes relating to<br>the nodes with matching agent names will be returned.
##### Keyword "fabrics"
Optional String. Only nodes with interfaces<br>in specified fabrics will be returned.
##### Keyword "not_fabrics"
Optional String. Only nodes with<br>interfaces not in specified fabrics will be returned.
##### Keyword "vlans"
Optional String. Only nodes with interfaces in<br>specified VLANs will be returned.
##### Keyword "not_vlans"
Optional String. Only nodes with interfaces<br>not in specified VLANs will be returned.
##### Keyword "subnets"
Optional String. Only nodes with interfaces<br>in specified subnets will be returned.
##### Keyword "not_subnets"
Optional String. Only nodes with<br>interfaces not in specified subnets will be returned.
##### Keyword "link_speed"
Optional String. Only nodes with<br>interfaces with link speeds greater than or equal to link_speed will<br>be returned.
##### Keyword "status"
Optional String. Only nodes with specified<br>status will be returned.
##### Keyword "pod"
Optional String. Only nodes that belong to a<br>specified pod will be returned.
##### Keyword "not_pod"
Optional String. Only nodes that don't<br>belong to a specified pod will be returned.
##### Keyword "pod_type"
Optional String. Only nodes that belong to<br>a pod of the specified type will be returned.
##### Keyword "not_pod_type"
Optional String. Only nodes that don't<br>belong a pod of the specified type will be returned.
##### Keyword "devices"
Optional String. Only return nodes which<br>have one or more devices containing the following constraints in the<br>format key=value[,key2=value2[,…]]<br><br>Each key can be one of the following:<br><br>- ``vendor_id``: The device vendor id<br>- ``product_id``: The device product id<br>- ``vendor_name``: The device vendor name, not case sensitive<br>- ``product_name``: The device product name, not case sensitive<br>- ``commissioning_driver``: The device uses this driver during<br>commissioning.


Note: This command accepts JSON.


Assign nodes to a zone

```bash
maas $PROFILE rack-controllers set-zone [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Assigns a given node to a given zone.

##### Keyword "zone"
Optional String. The zone name.
##### Keyword "nodes"
Optional String. The node to add.


Note: This command accepts JSON.
