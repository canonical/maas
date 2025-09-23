This guide explains how to find, read, and filter MAAS logs. Logs are essential for troubleshooting, auditing, and understanding MAAS operations. You can access several types of logs:

- System logs: General controller and service behavior.
- Event logs: User and system actions, useful for debugging.
- Commissioning logs: Hardware discovery and setup information.
- Testing logs: Results from hardware and validation tests.
- Audit logs: User activity and configuration changes for accountability (including OS image changes).

> Prerequisites: Administrator access to the MAAS host, basic familiarity with `journalctl` (for MAAS 3.5+), and optional MAAS CLI access for filtering events/audits.

## System logs

### MAAS 3.5 and newer (systemd journal)

From version 3.5 onward, MAAS uses the `systemd` journal instead of writing logs to disk. This provides a centralized, real-time view.

#### Region controller

- Snap-based installation
  ```bash
  journalctl -u snap.maas.pebble -t maas-regiond
  ```
- Debian-based installation
  ```bash
  journalctl -u maas-regiond
  ```

#### Rack controller

- Snap-based installation
  ```bash
  journalctl -u snap.maas.pebble -t maas-rackd
  ```
- Debian-based installation
  ```bash
  journalctl -u maas-rackd
  ```

#### Agent

- Snap-based installation
  ```bash
  journalctl -u snap.maas.pebble -t maas-agent
  ```
- Debian-based installation
  ```bash
  journalctl -u maas-agent
  ```

#### API Server

- Snap-based installation
  ```bash
  journalctl -u snap.maas.pebble -t maas-apiserver
  ```
- Debian-based installation
  ```bash
  journalctl -u maas-apiserver
  ```

#### Filter logs by machine

Search by machine (hostname):
```bash
journalctl -u snap.maas.pebble -t maas-machine --since "-15m" MAAS_MACHINE_HOSTNAME=ace-cougar
```

### MAAS versions earlier than 3.5 (log files)

Before 3.5, MAAS wrote logs to files. Common locations include:

- Region controller: `/var/snap/maas/common/log/regiond.log` or `/var/log/maas/regiond.log`
- Rack controller: `/var/snap/maas/common/log/rackd.log` or `/var/log/maas/rackd.log`
- Proxy service: `/var/snap/maas/common/log/proxy/access.log`

Read logs with:
```bash
less /var/snap/maas/common/log/regiond.log
```


## Event logs

Event logs track system and user activity, helping you trace what happened in MAAS.

### Using the UI
1. Open *Machines*.
2. Select a machine and open the *Events* tab.
3. Click *View full history* for more detail.

### Using the CLI

Query events:
```bash
maas $PROFILE events query
```

Format with `jq` for readability:
```bash
maas $PROFILE events query | jq -r '(["HOSTNAME","TIMESTAMP","TYPE","DESCRIPTION"] | (., map(length*"-"))), (.events[] | [.hostname, .created, .type, .description // "-"]) | @tsv' | column -t -s $'	'
```


## Commissioning logs

Commissioning verifies whether MAAS can successfully interact with a machine, gather specs, and run setup tasks. Check these logs when a machine fails commissioning or stays stuck in Ready, hardware details are missing/incorrect, PXE boots fail, or custom commissioning scripts error out.

### Using the UI
1. Go to the machine’s Commissioning tab.
2. Click the log links for details.

### Using the CLI
```bash
maas $PROFILE node-script-result read $SYSTEM_ID $RESULTS
```


## Testing logs

Testing validates whether a machine is production-ready. Logs confirm hardware health and firmware/kernel compatibility.

### Using the CLI
```bash
maas $PROFILE node-script-result read $SYSTEM_ID type=smartctl-validate
```


## Audit logs (including OS image changes)

Audit logs track user actions and configuration changes. Use them to investigate failures or changes, monitor who modified settings, and support compliance.

> Note: New audit events exist for OS image auditing. Include these examples to track image imports, deletions, or changes to boot resources.

### Query audit events

List all audit events:
```bash
maas $PROFILE events query level=AUDIT
```

Filter audit logs:

- By hostname
  ```bash
  maas $PROFILE events query level=AUDIT hostname=your-hostname
  ```
- By MAC address
  ```bash
  maas $PROFILE events query level=AUDIT mac_address=00:11:22:33:44:55
  ```
- By system ID
  ```bash
  maas $PROFILE events query level=AUDIT id=system-id
  ```
- By zone
  ```bash
  maas $PROFILE events query level=AUDIT zone=your-zone
  ```
- By owner
  ```bash
  maas $PROFILE events query level=AUDIT owner=owner-username
  ```

### Limit and paginate

- Limit results
  ```bash
  maas $PROFILE events query level=AUDIT limit=10
  ```
- Continue after an event ID
  ```bash
  maas $PROFILE events query level=AUDIT after=event-id
  ```

### OS image auditing examples

Common descriptions/types you may see include image import, deletion, sync, and boot-resource updates. Examples:

```bash
# Show recent audit events related to images or boot resources (adjust regex as needed)
maas $PROFILE events query level=AUDIT limit=200   | jq -r '.events[] | select((.description|test("image|boot resource|boot-resource|import|delete|sync"; "i"))) | "\(.created) \(.user) \(.type) \(.description)"'

# Filter by event type if your version provides image/audit-specific types
maas $PROFILE events query level=AUDIT type=BOOT_RESOURCE_UPDATED limit=100
maas $PROFILE events query level=AUDIT type=BOOT_RESOURCE_IMPORTED limit=100
maas $PROFILE events query level=AUDIT type=BOOT_RESOURCE_DELETED limit=100

# Narrow to a specific OS or release name in the description
maas $PROFILE events query level=AUDIT limit=200   | jq -r '.events[] | select((.description|test("ubuntu.*22\.04|focal|jammy"; "i"))) | "\(.created) \(.user) \(.type) \(.description)"'
```

> If your environment uses custom image mirrors or proxies, include those identifiers in your filters (e.g., `mirror`, `usn`, `daily`, `hwe`).

### Audit a machine lifecycle

Collect logs over time for one machine:
```bash
maas $PROFILE events query level=AUDIT hostname=your-hostname limit=1000 > /tmp/audit-data
```
Analyze `/tmp/audit-data` to see lifecycle changes for that host.


## Verification

> This section adopts your proposed wording for the reviewer’s second comment.

1) Verify MAAS services are emitting logs in real time

Snap installs:

```bash
# Region + rack logs, live tail (press Ctrl-C to stop)
sudo journalctl -f -u snap.maas.regiond -u snap.maas.rackd
```

Deb/package installs:

```bash
sudo journalctl -f -u maas-regiond -u maas-rackd
```

Success criteria: Within a few seconds of UI/CLI activity, you see new INFO/DEBUG entries (timestamps increasing).

Optional narrowing:
```bash
# Last 5 minutes, info and above
sudo journalctl --since -5m -p info -u snap.maas.regiond -u snap.maas.rackd
```

If nothing appears: confirm the right unit names, then run `sudo maas status` and check that region/rack are RUNNING.

2) Confirm commissioning and testing logs exist after running workflows

Trigger commissioning (example):

```bash
# Replace with your machine's system_id
SYS=ab/cdefg
maas $PROFILE machine commission $SYS
```

UI path: Machines → <machine> → Logs → expect new entries for Commissioning (and Hardware testing if enabled).

CLI spot-check recent events:
```bash
# Recent events for this machine (adjust limit as needed)
maas $PROFILE events query machine=$SYS limit=50 | jq -r '.events[] | "\(.created) \(.type) \(.description)"'
```

Success criteria: You see event types like *Commissioning*, *Commissioning complete*, *Testing* (if selected), with current timestamps.

If commissioning doesn’t produce logs: verify the machine PXE boots into the ephemeral image, and that rack connectivity to region is healthy.

3) Run audit queries and verify expected user activity

Examples to prove audit trail is recording actions:

```bash
# Filter by a specific user (replace $USER_EMAIL or username)
maas $PROFILE events query user=$USER_EMAIL limit=20 | jq -r '.events[] | "\(.created) \(.type) \(.description)"'

# Grep for login/config changes in the last 15 minutes
SINCE=$(date -Is -d '-15 minutes')
maas $PROFILE events query since="$SINCE" limit=200   | jq -r '.events[] | select((.description|test("login|set-config|Create|Delete"; "i"))) | "\(.created) \(.user) \(.type) \(.description)"'
```

Success criteria: You can point to concrete records: a login, an image import, a DHCP change, a machine action, with correct user and time.

If filters are unfamiliar: run `maas $PROFILE events query --help` to see supported parameters in your MAAS version.

4) (Optional) network service logs (when relevant)

If validating DHCP/DNS behavior, also tail those services:

Snap installs (named via bind9 in regiond):
```bash
sudo journalctl -f -u bind9
```

Deb/package installs (if isc-dhcp-server is used):
```bash
sudo journalctl -f -u isc-dhcp-server
```

Success criteria: `DHCPDISCOVER/DHCPOFFER/DHCPACK` and DNS query lines appear during commissioning or testing.


## Next steps

- Learn [how to monitor MAAS in real time](https://canonical.com/maas/docs/how-to-monitor-maas).
- Investigate ways to [secure MAAS effectively](https://canonical.com/maas/docs/how-to-enhance-maas-security).
