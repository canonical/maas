MAAS logs help you find issues, spot configuration mistakes, and audit the use of your system. Several types of logs are supported, including:

- System logs
- Event logs
- Commissioning logs
- Testing logs
- Audit event logs

Each of these has a specific purpose, as described in this document.

## Checking Logs in Systemd (MAAS 3.5 and Newer)

Understanding what MAAS is doing under the hood is critical when troubleshooting unexpected behavior — whether a machine fails to deploy, a controller won't respond, or an API call returns errors. Starting with version 3.5, MAAS uses `systemd` journal logs instead of log files written to disk. This change offers a more efficient and centralized way to inspect logs, in context, in real time.

### Region Controller Logs

 - Snap: `journalctl -u snap.maas.pebble -t maas-regiond`

 - Debian: `journalctl -u maas-regiond`

### Rack Controller Logs

 - `Snap: journalctl -u snap.maas.pebble -t maas-rackd`

 - `Debian: journalctl -u maas-rackd`

### Agent Logs

 - Snap: `journalctl -u snap.maas.pebble -t maas-agent`

 - Debian: `journalctl -u maas-agent`

### API Server Logs

 - Snap: `journalctl -u snap.maas.pebble -t maas-apiserver`

 - Debian: `journalctl -u maas-apiserver`

### Filtering Logs by Machine Name

To search for logs by machine name (hostname):

```
journalctl -u snap.maas.pebble -t maas-machine --since "-15m" MAAS_MACHINE_HOSTNAME=ace-cougar
```

## Checking Logs Before MAAS 3.5

Before version 3.5, MAAS saved logs in custom files. Here are some examples:

 - Region Controller: `/var/snap/maas/common/log/regiond.log` or `/var/log/maas/regiond.log`

 - Rack Controller: `/var/snap/maas/common/log/rackd.log` or `/var/log/maas/rackd.log`

 - Proxy: `/var/snap/maas/common/log/proxy/access.log`

### Using the less Command to Read Logs

```
less /var/snap/maas/common/log/regiond.log
```

## How to Read Event Logs

### Using the UI

 1. Go to the Machines list in the UI.

 2. Click on a machine and select the Events tab.

To see more details, click *View full history*.

### Using the Command Line

```
maas $PROFILE events query
```

### Formatting Event Logs with jq

To format the output neatly with jq:

```
maas admin events query | jq -r '(["HOSTNAME","TIMESTAMP","TYPE","DESCRIPTION"] | (., map(length*"-"))), (.events[] | [.hostname, .created, .type, .description // "-"]) | @tsv' | column -t -s $'\t'
```

## How to Read Commissioning Logs

Commissioning is the first real test of whether MAAS can interact successfully with your machine. It verifies hardware, applies the base configuration, and gathers critical info like CPU count, RAM, disk layout, and NICs.

When commissioning struggles or fails, commissioning logs help you to:

- Understand hardware discovery issues: If a machine shows incomplete specs or can't be used for deployment, the logs may reveal missing drivers, unresponsive disks, or incompatible firmware.
- Debug custom commissioning scripts: Running your own scripts? Commissioning logs are your best source for errors, output, and system state during execution.
- Diagnose PXE/networking issues: If the machine never commissions successfully, logs often contain clues — like DHCP failures, network interface errors, or incorrect boot images.
- Check package or script failures: Logs will reveal if MAAS couldn't install key packages, failed to mount volumes, or hit permission issues.

You should check commissioning logs when: 

- A newly added machine won't move past "Ready"
- Commissioning fails with a generic error
- Hardware details (CPU, disk, RAM) are missing or incorrect
- You are testing or troubleshooting custom commissioning scripts
- You see networking issues during PXE boot or image fetch

### Using the UI

 1. Go to the Commissioning tab of a machine.

 2. Click the links to see the detailed logs.

### Using the command line

```
maas $PROFILE node-script-result read $SYSTEM_ID $RESULTS
```

## How to read testing logs

Testing logs are the final gatekeepers in the MAAS lifecycle. They help you identify whether your machine is usable for real workloads. Often skipped over, they can save you a world of trouble when hardware flakiness or misconfiguration happens.

Testing confirms whether the machine is actually functioning as expected, not just booting.  It verify critical hardware functionality, validates storage health, and confirms firmware and kernel compatibility.

Test logs can contain any sort of test you may add, but the general form of the command is:

```bash
maas $PROFILE node-script-result read $SYSTEM_ID type=smartctl-validate
```

## Auditing MAAS

MAAS is often a shared resource, when something changes or breaks, you need to know who may have taken unexpected action. Audit logs help you:

- Track configuration changes
- Monitor user activity
- Investigate failures or unauthorized actions
- Maintain compliance or accountability

You check audit logs when:

- A machine config changes unexpectedly
- Network settings or VLANs were modified, breaking connectivity
- A deployment fails and you suspect human error
- You're in a shared MAAS environment and need to confirm who changed what
- During a security review or internal audit

The following commands will help you use auditing productively.

### List audit events

To get a list of MAAS audit events, you can use the following MAAS CLI command:

```nohighlight
$ maas $PROFILE events query level=AUDIT
```

This command will list all audit events. The output will include details such as username, hostname, date, and event description.

### Filter events by hostname

To filter audit events by a specific hostname, use the following MAAS CLI command:

```nohighlight
$ maas $PROFILE events query level=AUDIT hostname=your-hostname
```

Replace `your-hostname` with the desired hostname. This command will list audit events specific to the provided hostname.

### Filter events by MAC

If you want to filter audit events by a specific MAC address, use this MAAS CLI command:

```nohighlight
$ maas $PROFILE events query level=AUDIT mac_address=00:11:22:33:44:55
```

Replace `00:11:22:33:44:55` with the MAC address you want to filter by. This command will display audit events related to the specified MAC address.

### Filter events by SYSID

To filter audit events by a specific system ID, use the following MAAS CLI command:

```nohighlight
$ maas $PROFILE events query level=AUDIT id=system-id
```

Replace `system-id` with the desired system ID. This command will list audit events specific to the provided system ID.

### Filter events by zone

If you want to filter audit events by a specific zone, use the following MAAS CLI command:

```nohighlight
$ maas $PROFILE events query level=AUDIT zone=your-zone
```

Replace `your-zone` with the desired zone name. This command will display audit events for machines in the specified zone.

### Filter events by owner

To filter audit events by the owner of the machine, use this MAAS CLI command:

```nohighlight
$ maas $PROFILE events query level=AUDIT owner=owner-username
```

Replace `owner-username` with the username of the machine's owner. This command will list audit events for machines owned by the specified user.

### Limit event count

You can limit the number of audit events displayed using the `limit` parameter. For example:

```nohighlight
$ maas $PROFILE events query level=AUDIT limit=10
```

This command will limit the output to the last 10 audit events. You can adjust the limit to your preference.

### Move event window

To display audit events occurring after a specific event ID, you can use the `after` parameter. For example:

```nohighlight
$ maas $PROFILE events query level=AUDIT after=event-id
```

Replace `event-id` with the ID of the event you want to start from. This command will display audit events that occurred after the specified event.

### Audit life-cycles

To audit a machine's life cycle, you can collect audit data for a specific machine over time. First, collect a significant amount of audit data for the machine using the hostname filter:

```nohighlight
$ maas $PROFILE events query level=AUDIT hostname=your-hostname limit=1000 > /tmp/audit-data
```

This command will retrieve a substantial number of audit events for the specified hostname and store them in a file named `audit-data`.

Next, you can analyze this data to track changes, actions, and events related to the machine's life cycle. This can help in troubleshooting and monitoring machine behavior over time.

