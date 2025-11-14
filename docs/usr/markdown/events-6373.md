List node events

```bash
maas $PROFILE events query [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List node events, optionally filtered by various criteria<br>via URL query parameters.

##### Keyword "hostname"
Optional String. An optional hostname. Only<br>events relating to the node with the matching hostname will be<br>returned. This can be specified multiple times to get events relating<br>to more than one node.
##### Keyword "mac_address"
Optional String. An optional list of MAC<br>addresses. Only nodes with matching MAC addresses will be returned.
##### Keyword "id"
Optional String. An optional list of system ids.<br>Only nodes with matching system ids will be returned.
##### Keyword "zone"
Optional String. An optional name for a physical<br>zone. Only nodes in the zone will be returned.
##### Keyword "agent_name"
Optional String. An optional agent name.<br>Only nodes with matching agent names will be returned.
##### Keyword "level"
Optional String. Desired minimum log level of<br>returned events. Returns this level of events and greater. Choose from:<br>AUDIT, CRITICAL, DEBUG, ERROR, INFO, WARNING. The default is INFO.
##### Keyword "limit"
Optional String. number of events to<br>return. Default 100. Maximum: 1000.
##### Keyword "before"
Optional String. event id. Defines<br>where to start returning older events.
##### Keyword "after"
Optional String. event id. Defines<br>where to start returning newer events.
##### Keyword "owner"
Optional String. If specified, filters the list<br>to show only events owned by the specified username.


Note: This command accepts JSON.
