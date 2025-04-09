Enter keyword arguments in the form `key=value`.

## List node events

```bash
maas $PROFILE events query [--help] [-d] [-k] [data ...] 
```

List node events, optionally filtered by various criteria via URL query parameters.

#### Keyword "hostname"
Optional String.  An optional hostname. Only events relating to the node with the matching hostname will be returned. This can be specified multiple times to get events relating to more than one node.

#### Keyword "mac_address"
Optional String. An optional list of MAC addresses.  Only nodes with matching MAC addresses will be returned.

#### Keyword "id"
Optional String. An optional list of system ids. Only nodes with matching system ids will be returned.

#### Keyword "zone"
Optional String. An optional name for a physical zone. Only nodes in the zone will be returned.

#### Keyword "agent_name"
Optional String. An optional agent name. Only nodes with matching agent names will be returned.

#### Keyword "level"
Optional String.  Desired minimum log level of returned events. Returns this level of events and greater. Choose from: AUDIT, CRITICAL, DEBUG, ERROR, INFO, WARNING. The default is INFO.

#### Keyword "limit"
Optional String. Optional number of events to return. Default 100.  Maximum: 1000.

#### Keyword "before"
Optional String. Optional event id.  Defines where to start returning older events.

#### Keyword "after"
Optional String. Optional event id.  Defines where to start returning newer events.

#### Keyword "owner"
Optional String. If specified, filters the list to show only events owned by the specified username.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |
