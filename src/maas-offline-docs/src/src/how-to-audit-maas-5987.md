> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/auditing-maas-operations" target = "_blank">Let us know.</a>*

This page provides concise procedures for working with MAAS audit events.

## List audit events

To get a list of MAAS audit events, you can use the following MAAS CLI command:

```nohighlight
$ maas $PROFILE events query level=AUDIT
```

This command will list all audit events. The output will include details such as username, hostname, date, and event description.

## Filter events by hostname

To filter audit events by a specific hostname, use the following MAAS CLI command:

```nohighlight
$ maas $PROFILE events query level=AUDIT hostname=your-hostname
```

Replace `your-hostname` with the desired hostname. This command will list audit events specific to the provided hostname.

## Filter events by MAC

If you want to filter audit events by a specific MAC address, use this MAAS CLI command:

```nohighlight
$ maas $PROFILE events query level=AUDIT mac_address=00:11:22:33:44:55
```

Replace `00:11:22:33:44:55` with the MAC address you want to filter by. This command will display audit events related to the specified MAC address.

## Filter events by SYSID

To filter audit events by a specific system ID, use the following MAAS CLI command:

```nohighlight
$ maas $PROFILE events query level=AUDIT id=system-id
```

Replace `system-id` with the desired system ID. This command will list audit events specific to the provided system ID.

## Filter events by zone

If you want to filter audit events by a specific zone, use the following MAAS CLI command:

```nohighlight
$ maas $PROFILE events query level=AUDIT zone=your-zone
```

Replace `your-zone` with the desired zone name. This command will display audit events for machines in the specified zone.

## Filter events by owner

To filter audit events by the owner of the machine, use this MAAS CLI command:

```nohighlight
$ maas $PROFILE events query level=AUDIT owner=owner-username
```

Replace `owner-username` with the username of the machine's owner. This command will list audit events for machines owned by the specified user.

## Limit event count

You can limit the number of audit events displayed using the `limit` parameter. For example:

```nohighlight
$ maas $PROFILE events query level=AUDIT limit=10
```

This command will limit the output to the last 10 audit events. You can adjust the limit to your preference.

## Move event window

To display audit events occurring after a specific event ID, you can use the `after` parameter. For example:

```nohighlight
$ maas $PROFILE events query level=AUDIT after=event-id
```

Replace `event-id` with the ID of the event you want to start from. This command will display audit events that occurred after the specified event.

## Audit life-cycles

To audit a machine's life cycle, you can collect audit data for a specific machine over time. First, collect a significant amount of audit data for the machine using the hostname filter:

```nohighlight
$ maas $PROFILE events query level=AUDIT hostname=your-hostname limit=1000 > /tmp/audit-data
```

This command will retrieve a substantial number of audit events for the specified hostname and store them in a file named `audit-data`.

Next, you can analyse this data to track changes, actions, and events related to the machine's life cycle. This can help in troubleshooting and monitoring machine behaviour over time.