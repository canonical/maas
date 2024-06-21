> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/using-network-tags" target = "_blank">Let us know.</a>*

This page explains how to use network tags in MAAS.

## Creating and tagging network interfaces (UI)

To add a tag to an interface, navigate to *Machines* > machine > *Network* > *Edit physical* > *Tags*. Enter your new tag and click *Save interface*.

## Erasing tags from on interface (UI)

To remove a tag from an interface, navigate to *Machines* > machine > *Network* > *Edit physical* > *Tags*. Click *X* next to the tag you want to remove, and choose *Save interface*.

## Viewing tags on an interface (UI)

To view the tags on an interface, navigate to *Machines* > machine > *Network* > *Edit physical* > *Tags*. Click *Cancel* when done.

## Discover your interface's ID (CLI)

Identify your network interfaces with a command akin to this:

```nohighlight
maas $PROFILE interfaces read $SYSTEM_ID \
| jq -r '(["mac_address","type","id","tags"]
|(.,map(length*"-"))),(.[]|[.mac_address,.type,.id,.tags[]])
|@tsv'| column -t
```

Example:

```nohighlight
maas admin interfaces read xn8taa \
| jq -r '(["mac_address","type","id","tags"]
|(.,map(length*"-"))),(.[]|[.mac_address,.type,.id,.tags[]])
|@tsv'| column -t
```

Expect output like:

```nohighlight
mac_address        type      id  tags
-----------        ----      --  ----
00:16:3e:18:7f:ee  physical  9   andrpko  plinko  cochise
```

## Adding tags (CLI)

Tag your network interface with this command format:

```nohighlight
maas $PROFILE interface add-tag $SYSTEM_ID $INTERFACE_ID tag=$TAG_NAME
```

Example:

```nohighlight
maas admin interface add-tag xn8taa 9 tag=farquar
```

You'll see a verbose JSON output revealing the changes.

## Deleting tags (CLI)

To exterminate a tag:

```nohighlight
maas $PROFILE interface remove-tag $SYSTEM_ID $INTERFACE_ID tag=$TAG_NAME
```

Example:

```nohighlight
maas admin interface remove-tag xn8taa 9 tag=farquar
```

You'll be greeted with a JSON output that confirms the tag's removal.

## Listing tags (CLI)

List all tags with:

```nohighlight
maas $PROFILE interfaces read $SYSTEM_ID \
| jq -r '(["mac_address","type","id","tags"]
|(.,map(length*"-"))),(.[]|[.mac_address,.type,.id,.tags[]])
|@tsv'| column -t
```

Example:

```nohighlight
maas admin interfaces read xn8taa \
| jq -r '(["mac_address","type","id","tags"]
|(.,map(length*"-"))),(.[]|[.mac_address,.type,.id,.tags[]])
|@tsv'| column -t
```

Expect output like:

```nohighlight
mac_address        type      id  tags
-----------        ----      --  ----
00:16:3e:18:7f:ee  physical  9   andrpko  plinko  cochise  farquar
```

## Single-interface tag viewing

To view tags on a specific interface:

```nohighlight
maas $PROFILE interface read $SYSTEM_ID $INTERFACE_ID \
| jq '.tags'
```

Example:

```nohighlight
maas admin interface read xn8taa 9 | jq '.tags'
```

Anticipate a JSON output displaying the tags.