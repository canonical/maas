Machines must be in the "Ready" state to be allocated.

To allocate a node:

* In the MAAS UI, select *Machines* > machine > *Take action* > *Allocate*. 

* Via the MAAS CLI, use the following commands:

```nohighlight
    maas $PROFILE machines allocate
```
    
    To allocate a specific node:
    
```nohighlight
    maas $PROFILE machines allocate system_id=$SYSTEM_ID
```