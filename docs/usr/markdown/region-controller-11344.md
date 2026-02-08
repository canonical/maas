Delete a region controller

```bash
maas $PROFILE region-controller delete [--help] [-d] [-k] system_id [data ...]

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
Deletes a region controller with the given system_id. A region controller cannot be deleted if it hosts pod virtual machines.<br>Use `force` to override this behavior. Forcing deletion will also<br>remove hosted pods.

##### Keyword "force"
Optional Boolean. Tells MAAS to override<br>disallowing deletion of region controllers that host pod virtual<br>machines.


Note: This command accepts JSON.


Get system details

```bash
maas $PROFILE region-controller details [--help] [-d] [-k] system_id

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





Get power parameters

```bash
maas $PROFILE region-controller power-parameters [--help] [-d] [-k] system_id

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





Read a node

```bash
maas $PROFILE region-controller read [--help] [-d] [-k] system_id

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





Update a region controller

```bash
maas $PROFILE region-controller update [--help] [-d] [-k] system_id [data ...]

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
Updates a region controller with the given system_id.

##### Keyword "description"
Optional String. The new description for<br>this given region controller.
##### Keyword "power_type"
Optional String. The new power type for<br>this region controller. If you use the default value, power_parameters<br>will be set to the empty string. Available to admin users. See the<br>`Power types`_ section for a list of the available power types.
##### Keyword "power_parameters_skip_check"
Optional Boolean. Whether<br>or not the new power parameters for this region controller should be<br>checked against the expected power parameters for the region<br>controller's power type ('true' or 'false'). The default is 'false'.
##### Keyword "zone"
Optional String. Name of a valid physical zone<br>in which to place this region controller.


Note: This command accepts JSON.


MAC address registered

```bash
maas $PROFILE region-controllers is-registered [--help] [-d] [-k] [data ...]

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


List Nodes visible to the user

```bash
maas $PROFILE region-controllers read [--help] [-d] [-k] [data ...]

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
Optional String. Only nodes that don't<br>belong to a pod of the specified type will be returned.
##### Keyword "devices"
Optional String. Only return nodes which<br>have one or more devices containing the following constraints in the<br>format key=value[,key2=value2[,…]]<br><br>Each key can be one of the following:<br><br>- ``vendor_id``: The device vendor id<br>- ``product_id``: The device product id<br>- ``vendor_name``: The device vendor name, not case sensitive<br>- ``product_name``: The device product name, not case sensitive<br>- ``commissioning_driver``: The device uses this driver during<br>commissioning.
##### Keyword "arch"
Optional String. Only nodes with the specified<br>architecture will be returned.
##### Keyword "not_arch"
Optional String. Only nodes without the<br>specified architecture will be returned.
##### Keyword "cpu_speed"
Optional String. Only nodes with CPUs<br>running at the specified speed (in MHz) will be returned.
##### Keyword "deployment_target"
Optional String. Only nodes with<br>the specified deployment target will be returned.
##### Keyword "not_deployment_target"
Optional String. Only nodes<br>without the specified deployment target will be returned.
##### Keyword "fabric_classes"
Optional String. Attached to fabric<br>with specified classes.
##### Keyword "not_fabric_classes"
Optional String. Not attached to<br>fabric with specified classes.
##### Keyword "interfaces"
Optional String. Only nodes with<br>interfaces matching the specified constraints will be returned.
##### Keyword "not_hostname"
Optional String. Hostnames to ignore.
##### Keyword "not_id"
Optional String. System IDs to ignore.
##### Keyword "not_domain"
Optional String. Domain names to ignore.
##### Keyword "not_agent_name"
Optional String. Excludes nodes with<br>events matching the agent name.
##### Keyword "not_in_pool"
Optional String. Only nodes not in the<br>specified resource pools will be returned.
##### Keyword "not_in_zone"
Optional String. Not in zone.
##### Keyword "not_owner"
Optional String. Only nodes not owned by<br>the specified users will be returned.
##### Keyword "not_power_state"
Optional String. Only nodes not in<br>the specified power states will be returned.
##### Keyword "not_simple_status"
Optional String. Exclude nodes<br>with the specified simplified status.
##### Keyword "not_status"
Optional String. Exclude nodes with the<br>specified status.
##### Keyword "not_tags"
Optional String. Not having tags.
##### Keyword "owner"
Optional String. Only nodes owned by the<br>specified users will be returned.
##### Keyword "power_state"
Optional String. Only nodes in the<br>specified power states will be returned.
##### Keyword "simple_status"
Optional String. Only includes nodes<br>with the specified simplified status.
##### Keyword "storage"
Optional String. Only nodes with storage<br>matching the specified constraints will be returned.
##### Keyword "system_id"
Optional String. Only nodes with the<br>specified system IDs will be returned.
##### Keyword "tags"
Optional String. Only nodes with the specified<br>tags will be returned.


Note: This command accepts JSON.


Assign nodes to a zone

```bash
maas $PROFILE region-controllers set-zone [--help] [-d] [-k] [data ...]

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
