> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/understanding-audit-events" target = "_blank">Let us know.</a>*

MAAS audit logs provide detailed records of changes in machines, users, and settings. The `AUDIT` level logs are particularly useful for tracing historical changes in a MAAS instance. They are crucial for system integrity, troubleshooting, compliance, and governance.

## Fetch audit events

Use the `maas` CLI `events query` command to retrieve audit logs. Fetch all audit logs with:

```nohighlight
maas $PROFILE events query level=AUDIT
```

For the latest 20 audit events:

```nohighlight
maas $PROFILE events query level=AUDIT limit=20 after=0
```

## Parse the output

Audit logs are in JSON format, suitable for parsing with tools like `jq`. For example:

```nohighlight
maas $PROFILE events query level=AUDIT | jq -r '.events[] | {user, node, action}'
```

Alternatively, use text processing utilities like `grep`, `cut`, `sort`, and `sed` for analysis.

## Audit log structure

Audit logs typically follow a verb/noun structure. Examples include:

- `Started testing on 'example-node'`
- `Marked 'old-node' broken`
- `Deleted the machine 'retired-system'`

## Node audit types

Audit logs detail node activities including commissioning phases, test results, deployment statuses, and actions like acquiring, rescuing, and deleting.

## User audit types

Audit logs also track user activities, account modifications, system configuration changes, and updates to scripts or DHCP snippets.

## Filtering output

Refine audits using filters in the `events query` command. For events related to a specific node:

```nohighlight
maas $PROFILE events query hostname=my-node
```

For delete actions by a specific user:

```nohighlight
maas $PROFILE events query username=jane level=AUDIT | grep "Deleted "
```

Combining filters yields more targeted audit records, aiding in tailored governance.

## Keeping track

MAAS audit logs are essential for understanding system history. Effectively querying, filtering, and interpreting these logs are key skills for system troubleshooting, compliance, and oversight.