> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/reviewing-audit-logs" target = "_blank">Let us know.</a>*

Audit events are a subset of the MAAS event logs.  This page provides reference material for those who want to review and report on events designated as MAAS audit events.

## Auditing MAAS

MAAS audit events can be viewed using the CLI with a command similar to the following:

```nohighlight
maas $PROFILE events query level=AUDIT
```

Such a command would produce JSON output like this:


These MAAS audit events consist of the following information:

- **username**: the name of the user whose actions triggered the event.  This field is frequently blank, since many recordable events are triggered by MAAS and not by a specific user.
- **node**: this is the `$SYSTEM_ID` frequently used in the CLI to reference node.  This field is filled if a particular node participated in the event, even if the node did not trigger that event.  
- **hostname**: this is the node which triggered the event.  Generally, this will be the name of the region controller, the name of a machine, or blank.  Blank entries are events triggered by MAAS itself, such as `Starting rack boot image import`, which are not triggered by node. 
- **id**: a unique ID number assigned to table records as a primary key.
- **level**: the level of event, such as AUDIT, DEBUG, etc.
- **created**: the timestamp when this event entry was created.
- **description**: a long text description of what took place. This field is almost always populated; this is the primary information used for auditing MAAS events.
- **type**: this is the type of event that occurred, as shown in the following table.

|               name               |                 description                |
|---------------------------------|----------------------------------------------|
| AUTHORISATION | Authorisation |
| IMAGES | Images |
| NETWORKING | Networking |
| NODE | Node |
| NODE_HARDWARE_SYNC_BLOCK_DEVICE | Node Block Device hardware sync state change |
| NODE_HARDWARE_SYNC_BMC | Node BMC hardware sync state change |
| NODE_HARDWARE_SYNC_CPU | Node CPU hardware sync state change |
| NODE_HARDWARE_SYNC_INTERFACE | Node Interface hardware sync state change |
| NODE_HARDWARE_SYNC_MEMORY | Node Memory hardware sync state change |
| NODE_HARDWARE_SYNC_PCI_DEVICE | Node PCI Device hardware sync state change |
| NODE_HARDWARE_SYNC_USB_DEVICE | Node USB Device hardware sync state change |
| POD | Pod |
| SETTINGS | Settings |
| TAG | Tag |
| ZONES | Zones |

For information on how to use these audit events to answer specific questions, see [How to work with audit event logs](/t/how-to-audit-maas/5987).