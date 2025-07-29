Understanding MAAS events is crucial for debugging and verifying system functionality. These events represent changes in MAAS components like controllers, networks, or machines, triggered internally, by external factors, or through user actions such as machine commissioning.

## Viewing events

1. **MAAS Logs**: Offer raw, detailed data, accessible directly from the file system.
2. **UI Event Log**: Provides a summarised view through a user-friendly interface.
3. **CLI `events query` Command**: Quick, text-based overview of events.

Each source varies in detail and perspective. Here's an example related to a node named "fun-zebra".

## MAAS log sample

```nohighlight
maas.log:2022-09-29T15:04:07.795515-05:00 neuromancer maas.node: [info] fun-zebra: Status transition from COMMISSIONING to TESTING
maas.log:2022-09-29T15:04:17.288763-05:00 neuromancer maas.node: [info] fun-zebra: Status transition from TESTING to READY
```

## CLI output

```nohighlight
{
    "username": "unknown",
    "node": "bk7mg8",
    "hostname": "fun-zebra",
    "id": 170,
    "level": "INFO",
    "created": "Thu, 29 Sep. 2022 20:04:17",
    "type": "Ready",
    "description": ""
},
{
    "username": "unknown",
    "node": "bk7mg8",
    "hostname": "fun-zebra",
    "id": 167,
    "level": "INFO",
    "created": "Thu, 29 Sep. 2022 20:04:07",
    "type": "Running test",
    "description": "smartctl-validate on sda"
}
```

## UI log

| Time | Event |
|---|---|
|Thu, 29 Sep. 2022 20:04:17 | Node changed status - From 'Testing' to 'Ready' |
|Thu, 29 Sep. 2022 20:04:07 | Node changed status - From 'Commissioning' to 'Testing' |

These sources, while all reliable, offer different levels of detail. Choosing the right one can significantly streamline debugging and system checks.

## About audit events

MAAS audit logs provide detailed records of changes in machines, users, and settings. The `AUDIT` level logs are particularly useful for tracing historical changes in a MAAS instance. They are crucial for system integrity, troubleshooting, compliance, and governance.

### Fetch audit events

Use the `maas` CLI `events query` command to retrieve audit logs. Fetch all audit logs with:

```nohighlight
maas $PROFILE events query level=AUDIT
```

For the latest 20 audit events:

```nohighlight
maas $PROFILE events query level=AUDIT limit=20 after=0
```

### Parse the output

Audit logs are in JSON format, suitable for parsing with tools like `jq`. For example:

```nohighlight
maas $PROFILE events query level=AUDIT | jq -r '.events[] | {username, node, description}'
```

Alternatively, use text processing utilities like `grep`, `cut`, `sort`, and `sed` for analysis.

### Audit log structure

Audit logs typically follow a verb/noun structure. Examples include:

- `Started testing on 'example-node'`
- `Marked 'old-node' broken`
- `Deleted the machine 'retired-system'`

### Node audit types

Audit logs detail node activities including commissioning phases, test results, deployment statuses, and actions like acquiring, rescuing, and deleting.

### User audit types

Audit logs also track user activities, account modifications, system configuration changes, and updates to scripts or DHCP snippets.

### Filtering output

Refine audits using filters in the `events query` command. For events related to a specific node:

```nohighlight
maas $PROFILE events query hostname=my-node
```

For delete actions by a specific user:

```nohighlight
maas $PROFILE events query username=jane level=AUDIT | grep "Deleted "
```

Combining filters yields more targeted audit records, aiding in tailored governance.

### Keeping track

MAAS audit logs are essential for understanding system history. Effectively querying, filtering, and interpreting these logs are key skills for system troubleshooting, compliance, and oversight.
