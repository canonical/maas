> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/delving-into-maas-logging-practices" target = "_blank">Let us know.</a>*
	
This page describes basic MAAS logging operations. For more details, refer to these reference pages:

- [Commissioning logs](/t/how-to-read-commissioning-logs/5248)
- [Test logs](/t/how-to-interpret-testing-logs/5314)
- [Event logs](/t/how-to-read-event-logs/5252)
- [Audit event logs](/t/how-to-review-audit-logs/5256)

## Logging updates in MAAS 3.5

In 3.5, the MAAS snap uses the [Pebble](https://github.com/canonical/pebble) service manager instead of `supervisord`. This means that the `systemd` component was renamed to `snap.maas.pebble.service`.  It contains Pebble logs, as well as intercepted stdout of the services running under Pebble.  The region and rack logs are cached there, as well (i.e., `regiond.log` and `rackd.log` are no more -- supervisord was redirecting the stdout of the respective services).

Here is a per-service breakdown how logging works in MAAS 3.5:

### Pebble

Pebble logs to `stdout`, redirecting the services to `stdout` if run with `--verbose` (currently in use).  It logs additional debug information when run with envvar `PEBBLE_DEBUG=1` (currently in use).

#### Log entry format

```nohighlight
2023-07-24T11:12:25.495Z [pebble] GET /v1/services?names=bind9 57.716µs
2023-07-24T11:12:26.392Z [SERVICE_NAME] SERVICE STDOUT
```

#### Commands to access the log

To access only the Pebble logs:

```nohighlight
journalctl -u snap.maas.pebble.service --case-sensitive -g "^[0-9TZ:.-]{24} \[pebble\]"
```

To access Pebble and its services logs:

```nohighlight
journalctl -u snap.maas.pebble.service
```

### Regiond

Regiond logs to `stdout`, redirected to journalctl by Pebble.

#### Own log format

```nohighlight
2023-07-25 07:23:28 maasserver.rpc.regionservice: [info] Message
```

#### Pebble-proxied log format

```nohighlight
2023-07-25T07:23:28.730Z [regiond] 2023-07-25 07:23:28 maasserver.rpc.regionservice: [info] Message
```

#### Commands to access the log

```nohighlight
journalctl -u snap.maas.pebble.service --case-sensitive -g "^[0-9TZ:.-]{24} \[regiond\]"
```

### Rackd

Rackd logs to `stdout`, redirected to journalctl by Pebble.

#### Own log format

```nohighlight
2023-06-23 13:54:46 provisioningserver.rpc.clusterservice: [info] Message
```

#### Pebble-proxied log format

```nohighlight
2023-06-23T13:54:46.391Z [rackd] 2023-06-23 13:54:46 provisioningserver.rpc.clusterservice: [info] Message
```

#### Commands to access the log

```nohighlight
journalctl -u snap.maas.pebble.service --case-sensitive -g "^[0-9TZ:.-]{24} \[rackd\]"
```

### API Server

The API server logs to `stdout`, redirected to journalctl by Pebble.

#### Own log format

```nohighlight
INFO:     Started server process [24428]
```

#### Pebble-proxied log format

```nohighlight
2023-07-24T10:25:37.602Z [apiserver] INFO:     Started server process [24428]
```

#### Commands to access the log

```nohighlight
journalctl -u snap.maas.pebble.service --case-sensitive -g "^[0-9TZ:.-]{24} \[apiserver\]"
```

## HTTP (nginx)

HTTP logs to its own files (`/var/snap/maas/common/log/http/(access|error).log`), while `stdout` (redirected by Pebble) contains only critical errors that cannot be redirected to the error log.

#### Pebble-proxied log format

```nohighlight
2023-06-23T13:54:46.391Z [http] nginx: [alert] could not open error log file
```

##### Own logs

```nohighlight
less /var/snap/maas/common/log/http/access.log (or error.log)
```

##### `stdout` redirected by Pebble:

```nohighlight
journalctl -u snap.maas.pebble.service --case-sensitive -g "^[0-9TZ:.-]{24} \[http\]"
```

### Proxy (squid)

The squid proxy logs to its own files (`/var/snap/maas/common/log/proxy/(access|cache|store).log`), while `stdout` (redirected by Pebble) contains init messages and errors.

#### Pebble proxied log format:


```nohighlight
2023-06-23T13:54:41.114Z [proxy] 2023/06/23 13:54:41| Starting Squid Cache version 5.2
```

##### Own logs

```nohighlight
less /var/snap/maas/common/log/proxy/access.log (or other log)
```

##### `stdout` redirected by Pebble:

```nohighlight
journalctl -u snap.maas.pebble.service --case-sensitive -g "^[0-9TZ:.-]{24} \[proxy\]"
```

### NTP (chrony)

At first glance, `chrony` seems to have a separate directory for log files (`/var/snap/maas/common/log/chrony`), but no log files are typically present there.  Instead, used `stdout` (redirected by Pebble), which contains init message and errors.

#### Pebble proxied log format:


```nohighlight
2023-06-26T12:48:01.272Z [ntp] 2023-06-26T12:48:01Z chronyd version 4.2 starting
```

#### Own log format


```nohighlight
2023-06-26T12:48:01Z chronyd version 4.2 starting
```

##### `stdout` redirected by Pebble:

```nohighlight
journalctl -u snap.maas.pebble.service --case-sensitive -g "^[0-9TZ:.-]{24} \[ntp\]"
```

### DNS (bind9)

DNS logs everything to `stdout`, ignoring any configuration parameters defined in the snap. As usual, `stdout` is redirected by Pebble.

#### Pebble proxied log format:


```nohighlight
2023-06-23T13:54:43.268Z [bind9] 23-Jun-2023 13:54:43.264 BIND 9 is maintained by Internet Systems Consortium
```

#### Own log format

```nohighlight
23-Jun-2023 13:54:43.264 BIND 9 is maintained by Internet Systems Consortium
```

#### Commands to access the log

```nohighlight
journalctl -u snap.maas.pebble.service --case-sensitive -g "^[0-9TZ:.-]{24} \[bind9\]"
```

### Syslog (rsyslog)

Syslog logs machines enlistment and boot syslogs to `/var/snap/maas/common/log/rsyslog/%HOSTNAME%/`, and logs various MAAS-tagged records to `/var/snap/maas/common/log/maas.log`. Otherwise, `stdout` (redirected by Pebble) contains internal messages/errors.

#### Pebble proxied log format:


```nohighlight
2023-07-24T05:38:56.522Z [syslog] Message
```

#### Own log format

```nohighlight
<some message>
```

##### Own logs

```nohighlight
less /var/snap/maas/common/log/rsyslog/PATH/TO/LOG
```

##### `stdout` redirected by Pebble:

```nohighlight
journalctl -u snap.maas.pebble.service --case-sensitive -g "^[0-9TZ:.-]{24} \[syslog\]"
```

### DHCP (dhcpd, dhcpd6)

DHCP logs everything through `syslogd`, while `stdout` (redirected by Pebble) contains init messages.  There is no particularly easy way to differentiate between `dhcpd` and `dhcpd6`, although you can `grep` for a “PID file: /var/snap/maas/common/maas/dhcp/dhcpd6?\.pid ” message, and then use the PID to filter logs in journal, like this:

```nohighlight
journalctl -et dhcpd -u snap.maas.pebble.service SYSLOG_PID=25799
```

#### Pebble proxied log format:


```nohighlight
2023-06-27T11:24:47.674Z [dhcpd] Internet Systems Consortium DHCP Server 4.4.1
```

#### Own log format 

```nohighlight
<plain old DHCP message>
```

##### Own logs

```nohighlight
journalctl -t dhcpd -u snap.maas.pebble.service
```

##### `stdout` redirected by Pebble:

```nohighlight
journalctl -u snap.maas.pebble.service --case-sensitive -g "^[0-9TZ:.-]{24} \[dhcpd\]"
```

## Remote syslog (3.4 UI) 

To enable remote logging, choose *Settings* > *Network* > *Syslog*, and enter your syslog server's IP/URL under *Remote syslog server to forward machine logs*.

## Remote syslog (3.3-- UI)

To enable remote logging, choose *Settings* > *Network services* > *Syslog*; add your syslog server's IP/UL; and click *Save*.

## Remote syslog (CLI)

```nohighlight
maas $PROFILE maas set-config name="remote_syslog" value="$SYSLOG_FQDN"
# Example for setting syslog server to 192.168.100.11:
maas $PROFILE maas set-config name="remote_syslog" value=192.168.100.11
# To reset to default (sending syslog to MAAS region controllers):
maas $PROFILE maas set-config name="remote_syslog" value="
```

**Note**: Only machine syslog information is forwarded, not MAAS controllers syslog files.

## Direct log access

Logs can be found at the following paths depending on your installation type (snap or package):

- Snap installation:
  - /var/snap/maas/common/log/maas.log
  - /var/snap/maas/common/log/regiond.log
  - /var/snap/maas/common/log/rackd.log
  - /var/snap/maas/common/log/rsyslog/$MACHINE_NAME/$RELEVANT_DATE/messages

- Package installation:
  - /var/log/maas/maas.log
  - /var/log/maas/regiond.log
  - /var/log/maas/rackd.log
  - /var/log/maas/rsyslog/$MACHINE_NAME/$RELEVANT_DATE/messages

Logs can be extensive and challenging to search. The MAAS web UI does not categorize events by type.

## Events query (CLI)

The most efficient way to review events is using the `events query` CLI sub-command. This command allows filtering and summarizing events. Use `jq` and various filters to simplify output interpretation.

## Basic queries

```nohighlight
maas $PROFILE events query
```

This command returns a lengthy JSON output, which can be simplified using `jq` and various filters, making it more readable.

## Using jq with events

A `jq` command example for readable output:

```nohighlight
maas $PROFILE events query limit=20 | jq -r '(["USERNAME","NODE","HOSTNAME","LEVEL","DATE","TYPE","EVENT"] | (., map(length*"-"))), (.events[] | [.username,.node,.hostname,.level,.created,.type,.description]) | @tsv' | column -t -s$'\t'
```

## Filter parameters

The `events query` command supports multiple filters:

- *hostname*: Events for a specific node hostname.
- *mac_address*: Events for nodes with specified MAC addresses.
- *id*: Events for nodes with specific system IDs.
- *zone*: Events for nodes in a particular zone.
- *level*: Filter by event level (AUDIT, CRITICAL, DEBUG, ERROR, INFO, WARNING).
- *limit*: Maximum number of events to return.
- *before/after*: Start returning events before or after a specific event ID.

Example usage of these filters can narrow down event listings significantly.

## Auditing finesse

Audit events, tagged with `AUDIT`, record MAAS configuration changes and machine state transitions. They're essential for tracking user actions and system updates, especially in multi-user environments.

Use audit events alongside `jq` and command-line text tools to analyze actions like machine deletions, configuration changes, and user activities. This can provide insights into system changes and help identify areas for attention or improvement.
