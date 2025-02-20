Availability zones (AZs) in MAAS improve fault tolerance, service performance, and power management by organizing resources across physical or network areas.

> *Learn more about [Availability zones](https://maas.io/docs/about-availability-zones)*

## List availability zones

**UI**
*Main menu* > *AZs*

**CLI**
```sh
maas $PROFILE zones read \
| jq -r '(["ZONE","NAME","DESCRIPTION"]
| (., map(length*"-"))), (.[] | [.id, .name, .description])
| @tsv' | column -t
```

Example output:
```sh
ZONE  NAME         DESCRIPTION
----  ----         -----------
5     BizOffice
1     default
4     Inventory
2     Medications
3     Payroll
6     ProServ
```

## Add an availability zone

**UI**
*Main menu* > *AZs* > *Add AZ* > Enter *Name*, *Description* > *Add AZ*.

**CLI**
```sh
maas $PROFILE zones create name=$ZONE_NAME description=$ZONE_DESCRIPTION
```

## Edit an availability zone

**UI**
*Main menu* > *AZs* > Select AZ > *Edit* > Update *Name*, *Description* > *Update AZ*.

**CLI**
```sh
maas $PROFILE zone update $OLD_ZONE_NAME name=$NEW_ZONE_NAME \
description=$ZONE_DESCRIPTION
```

## Delete an availability zone

**UI**
*Main menu* > *AZs* > Select zone > *Delete AZ* > *Delete AZ*.

**CLI**
```sh
maas $PROFILE zone delete $ZONE_NAME
```

## Assign a machine to an availability zone

**UI (MAAS 3.4)**
*Machines* > Select machines > *Categorise* > *Set zone* > Choose *Zone* > *Set zone for machine*.

**UI**
*Machines* > Select machines > *Take action* > *Set zone* > Choose *Zone* > *Set zone for machine*.

**CLI**
```sh
maas $PROFILE machines read | jq '.[] | .hostname, .system_id'
maas admin machine update $SYSTEM_ID zone=$ZONE_NAME
```
