This guide explains how to find, read, and filter MAAS logs. Logs are essential for troubleshooting, auditing, and understanding MAAS operations. You can access several types of logs:

- System logs: General controller and service behavior.
- Event logs: User and system actions, useful for debugging.
- Commissioning logs: Hardware discovery and setup information.
- Testing logs: Results from hardware and validation tests.
- Audit logs: User activity and configuration changes for accountability.

## Prerequisites

- Administrator privileges on the MAAS host.
- Familiarity with the `journalctl` command (MAAS 3.5+) or log files (< 3.5).
- Access to the MAAS CLI if filtering events or audits.

## System logs

### MAAS 3.5 and newer

From version 3.5 onward, MAAS uses the `systemd` journal instead of writing logs to disk. This provides a centralized, real-time log view.

#### Region Controller

- Snap install:
  ```bash
  journalctl -u snap.maas.pebble -t maas-regiond
  ```
- Debian install:
  ```bash
  journalctl -u maas-regiond
  ```

#### Rack Controller

- Snap install:
  ```bash
  journalctl -u snap.maas.pebble -t maas-rackd
  ```
- Debian install:
  ```bash
  journalctl -u maas-rackd
  ```

#### Agent

- Snap install:
  ```bash
  journalctl -u snap.maas.pebble -t maas-agent
  ```
- Debian install:
  ```bash
  journalctl -u maas-agent
  ```

#### API Server

- Snap install:
  ```bash
  journalctl -u snap.maas.pebble -t maas-apiserver
  ```
- Debian install:
  ```bash
  journalctl -u maas-apiserver
  ```

#### Filter logs by machine

Search by machine name (hostname):
```bash
journalctl -u snap.maas.pebble -t maas-machine --since "-15m" MAAS_MACHINE_HOSTNAME=ace-cougar
```

### MAAS versions earlier than 3.5

Before 3.5, MAAS wrote logs to files. Examples include:

- Region controller:
  `/var/snap/maas/common/log/regiond.log` or `/var/log/maas/regiond.log`

- Rack controller:
  `/var/snap/maas/common/log/rackd.log` or `/var/log/maas/rackd.log`

- Proxy service:
  `/var/snap/maas/common/log/proxy/access.log`

Read logs using:
```bash
less /var/snap/maas/common/log/regiond.log
```

## Event logs

Event logs track system and user activity, helping you trace what happened in MAAS.

### Using the UI

1. Open the Machines list.
2. Select a machine → open the Events tab.
3. Click View full history for more detail.

### Using the CLI

Query events:
```bash
maas $PROFILE events query
```

Format with `jq` for readability:
```bash
maas admin events query | jq -r '(["HOSTNAME","TIMESTAMP","TYPE","DESCRIPTION"] | (., map(length*"-"))), (.events[] | [.hostname, .created, .type, .description // "-"]) | @tsv' | column -t -s $'\t'
```

## Commissioning logs

Commissioning verifies whether MAAS can successfully interact with a machine, gather specs, and run setup tasks. Logs are essential when:

- A machine fails commissioning or stays stuck in “Ready.”
- Hardware details (CPU, RAM, disks, NICs) are missing or wrong.
- PXE/network boot fails.
- Custom commissioning scripts error out.

### Using the UI

1. Go to a machine’s Commissioning tab.
2. Click log links for details.

### Using the CLI

```bash
maas $PROFILE node-script-result read $SYSTEM_ID $RESULTS
```

## Testing logs

Testing validates whether a machine is production-ready. Logs confirm hardware health and firmware/kernel compatibility.

### Using the CLI

General test log command:
```bash
maas $PROFILE node-script-result read $SYSTEM_ID type=smartctl-validate
```

## Audit logs

Audit logs track user actions and configuration changes. Use them to:

- Investigate failures or changes.
- Monitor who modified settings.
- Support compliance or reviews.

### Query audit events

List all audit events:
```bash
maas $PROFILE events query level=AUDIT
```

Filter audit logs:

- By hostname:
  ```bash
  maas $PROFILE events query level=AUDIT hostname=your-hostname
  ```

- By MAC address:
  ```bash
  maas $PROFILE events query level=AUDIT mac_address=00:11:22:33:44:55
  ```

- By system ID:
  ```bash
  maas $PROFILE events query level=AUDIT id=system-id
  ```

- By zone:
  ```bash
  maas $PROFILE events query level=AUDIT zone=your-zone
  ```

- By owner:
  ```bash
  maas $PROFILE events query level=AUDIT owner=owner-username
  ```

### Limit and paginate

- Limit results:
  ```bash
  maas $PROFILE events query level=AUDIT limit=10
  ```

- Continue from an event ID:
  ```bash
  maas $PROFILE events query level=AUDIT after=event-id
  ```

### Audit machine lifecycle

Collect logs over time for one machine:
```bash
maas $PROFILE events query level=AUDIT hostname=your-hostname limit=1000 > /tmp/audit-data
```

Analyze the file `/tmp/audit-data` to see all lifecycle events for that machine.

## Verification

- Use `journalctl -f` to confirm logs are updating in real time.
- Confirm commissioning and testing logs exist after running workflows.
- Run audit queries and verify expected user activity appears.

## Next steps

- Learn [how to monitor MAAS in real time](https://canonical.com/maas/docs/how-to-monitor-maas).
- Investigate ways to [effectively secure MAAS](https://canonical.com/maas/docs/how-to-enhance-maas-security).
