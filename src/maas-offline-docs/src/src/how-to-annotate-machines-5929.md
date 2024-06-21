> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/annotating-machine-details" target = "_blank">Let us know.</a>*

Annotations in MAAS are potent tools for adding context and metadata to your machines. They act as supplementary data that allow you to identify, filter, and manage your machines more effectively. Essentially, annotations fall into two categories: 

1. Notes: These are always available, regardless of the machine's state.
2. Dynamic Annotations: These only exist when a machine is in an allocated or deployed state.

This page explains how to use notes and dynamic annotations.

> Dynamic annotations aren't supported in MAAS version 2.9 or earlier.

## Notes

Notes are persistent descriptions that stay with a machine throughout its life-cycle unless manually altered. You can manage notes through both the MAAS UI and CLI.

## Notes via UI

To add or modify notes via the MAAS UI:

1. Navigate to *Machines > Machine name > Configuration > Edit*.

2. Your existing notes appear in the *Note* section.

3. Add new or modify existing notes in the *Note* section.

4. Delete irrelevant notes from the same block.

5. Make sure to *Save changes* to confirm your actions.

## Notes via CLI

#### Identifying your machines

To determine machine identifiers, run the following command:

```nohighlight
maas $PROFILE machines read \
| jq -r '(["hostname","system_id"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id])
|@tsv' | column -t
```

#### Managing notes in CLI

You can add or modify a note as follows:

```nohighlight
maas $PROFILE machine update $SYSTEM_ID description="$NOTE"
```

To erase a note, just use an empty string:

```nohighlight
maas $PROFILE machine update $SYSTEM_ID description=""
```

## Dynamic annotations

Dynamic annotations are ephemeral data, tied to the operational states of allocated or deployed machines. These annotations are especially handy for tracking the live status of your workloads.

## Identifying eligible machines for dynamic annotations

To list machines that can receive dynamic annotations, execute:

```nohighlight
maas $PROFILE machines read \
| jq -r '(["hostname","system_id","status"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.status_name])
|@tsv' | column -t
```

## Setting dynamic annotations

You can define dynamic annotations using `key=value` pairs. To set one, use:

```nohighlight
maas $PROFILE machine set-owner-data $SYSTEM_ID $KEY=$VALUE
```

## Managing dynamic annotations

To change or remove a dynamic annotation, use the following commands:

- For changing: 
```nohighlight
maas $PROFILE machine set-owner-data $SYSTEM_ID $KEY=$NEW_VALUE
```

- For removing: 
```nohighlight
maas $PROFILE machine set-owner-data $SYSTEM_ID $KEY=""
```

## Listing dynamic annotations

To view all current dynamic annotations, run:

```nohighlight
maas $PROFILE machines read \
| jq -r '(["hostname","system_id","owner_data"]
|(.,map(length*"-"))),(.[]|[.hostname,.system_id,.owner_data[]])
|@tsv' | column -t
```

## Summary

Annotations in MAAS offer an additional layer of intelligence to your machine management. While notes provide a stable form of annotations, dynamic annotations offer a more fluid form of tracking, directly linked to your machine's operational status.