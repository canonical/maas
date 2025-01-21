> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/an-overview-of-maas-events" target = "_blank">Let us know.</a>*

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