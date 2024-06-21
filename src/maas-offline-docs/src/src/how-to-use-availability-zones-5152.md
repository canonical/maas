> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/use-availability-zones" target = "_blank">Let us know.</a>*

This page explains how to use availability zones with MAAS. You can learn about availability zones [elsewhere in this documentation set](/t/about-maas-networks/5084).

## List availability zones

To see a list of availability zones: 

* In the MAAS UI, select *AZs* from the top tab bar.

* Via the MAAS CLI, enter the following command:

```nohighlight
    maas $PROFILE zones read \
    | jq -r '(["ZONE","NAME","DESCRIPTION"]
    | (., map(length*"-"))), (.[] | [.id, .name, .description])
    | @tsv' | column -t
```
    
    which produces output similar to:

```nohighlight
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

To create an availability zone:

* In the MAAS UI, select *AZs* > *Add AZ* > enter *Name*,*Description* > *Add AZ*.

* Via the CLI, enter the following command:

```nohighlight
    maas $PROFILE zones create name=$ZONE_NAME description=$ZONE_DESCRIPTION
```
    
## Edit an availability zone

To edit an availability zone:

* In the MAAS UI, select *AZs* > <AZ name> > *Edit* > Update *Name*,*Description* > *Update AZ*.

* Via the MAAS CLI, enter a command similar to the following:

```nohighlight
    maas $PROFILE zone update $OLD_ZONE_NAME name=$NEW_ZONE_NAME \
    description=$ZONE_DESCRIPTION
```
    
## Delete an availability zone

To delete an availability zone:

* In the MAAS UI, select *AZs* > <zone name> > *Delete AZ* > *Delete AZ*.

* Via the MAAS CLI, enter a command like this:

```nohighlight
    maas $PROFILE zone delete $ZONE_NAME
```
    
## Assign a machine to an availability zone

To assign a machine to an availability zone:

* In the MAAS 3.4 UI, select *Machines* > choose machines > *Categorise* > *Set zone* > choose *Zone* > *Set zone for machine*.

* With the UI for all other MAAS versions, select *Machines* > choose machines > *Take action* > *Set zone* > choose *Zone* > *Set zone for machine*.

* Via the MAAS CLI, first retrieve the machine's system ID like this:

```nohighlight
    maas PROFILE machines read | jq '.[] | .hostname, .system_id'
```
    
    Then enter the following command, using the system ID you just retrieved:
    
```nohighlight
    maas admin machine update $SYSTEM_ID zone=$ZONE_NAME
```
    
## Deploy a machine in a particular zone (CLI)

To deploy in a particular zone:

1. First acquire the machine, assigning it to the particular zone:

```nohighlight
    maas $PROFILE machines allocate zone=$ZONE_NAME system_id=$SYSTEM_ID 
```
    
2. Then deploy the machine as normal:

```nohighlight
    maas $PROFILE machine deploy system_id=$SYSTEM_ID
```