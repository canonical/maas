
Events in MAAS record what’s happening inside the system — from machine state changes to user actions and configuration updates. Understanding them helps you:

- Debug commissioning and deployment issues.
- Verify that operations completed as expected.
- Maintain an audit trail for compliance and governance.

Events can be triggered by:
- Internal processes (e.g., a machine moving from commissioning to testing).
- External conditions (e.g., a controller restarting).
- User actions (e.g., acquiring or deleting a machine).


## Ways to view events

You can explore events in three different ways, depending on how much detail you need:

- MAAS logs (raw detail)
  Directly from the file system, with full context. Best for deep troubleshooting.

- CLI `events query` command (structured JSON)
  A quick way to filter and script against event data.

- UI Event Log (summary view)
  A user-friendly log of major events, easy to read at a glance.


## Examples

For a machine called `fun-zebra`:

Log file (`maas.log`)

```nohighlight
maas.log:2022-09-29T15:04:07.795515-05:00 neuromancer maas.node: [info] fun-zebra: Status transition from COMMISSIONING to TESTING
maas.log:2022-09-29T15:04:17.288763-05:00 neuromancer maas.node: [info] fun-zebra: Status transition from TESTING to READY
```

CLI output (`events query`)

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

UI event log

| Time | Event |
|------|-------|
| Thu, 29 Sep. 2022 20:04:17 | Node changed status – From *Testing* to *Ready* |
| Thu, 29 Sep. 2022 20:04:07 | Node changed status – From *Commissioning* to *Testing* |


## About audit events

In addition to standard events, MAAS generates audit events (`AUDIT` level) that focus on:

- Machine lifecycle changes (commissioning, deployment, deletion).
- User activity (logins, role changes, configuration edits).
- System settings (DHCP snippets, scripts, and more).

Audit logs are especially valuable for:
- Compliance and governance.
- Tracing historical changes.
- Reconstructing the timeline of a problem.


## Working with audit events

### Fetch audit events

```bash
# Get all audit logs
maas $PROFILE events query level=AUDIT

# Get the latest 20
maas $PROFILE events query level=AUDIT limit=20 after=0
```

### Parse the output

Audit logs are JSON, so you can pipe into `jq`:

```bash
maas $PROFILE events query level=AUDIT | jq -r '.events[] | {username, node, description}'
```

For simpler parsing, standard UNIX text tools (`grep`, `cut`, `sort`, `sed`) also work.

### Typical structure

Audit events usually follow a verb–noun pattern:

- `Started testing on 'example-node'`
- `Marked 'old-node' broken`
- `Deleted the machine 'retired-system'`

### Filtering

Narrow results by hostname or username:

```bash
# Show audit events for one machine
maas $PROFILE events query hostname=my-node

# Show delete actions by a user
maas $PROFILE events query username=jane level=AUDIT | grep "Deleted "
```

Filters can be combined for precise queries.


## Summary

- Events show what’s happening inside MAAS.
- Audit events add accountability and history.
- Logs, CLI, and UI each give a different perspective — pick the one that fits your need.
- Filtering and parsing make large event sets manageable.

## Next steps
- Discover [how to use logging](https://canonical.com/maas/docs/how-to-use-logging)
- Scan the [MAAS logging reference](https://canonical.com/maas/docs/maas-logging-reference) to discover the various types of logs available in MAAS
