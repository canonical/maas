> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/how-to-use-resource-pools" target = "_blank">Let us know.</a>

Administrators can manage MAAS resource pools to group machines in sensible ways.  All MAAS installations have a resource pool named "default," to which MAAS automatically adds new machines.

## Add a resource pool 

To add a resource pool to MAAS:

* In the MAAS 3.4 UI, choose *Organisation > Pools > Add pool*; enter *Name* and *Description*; select *Save pool*.

* With the UI in all other versions of MAAS, choose *Resource* > *Add pool*; enter *Name* and *Description*; select *Add pool*.

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE resource-pools create name=$NAME description="$DESCRIPTION"
```

## Delete a resource pool

If you delete a resource pool, all machines that belong to that resource pool will return to the default pool.  There is no confirmation dialogue; pools are deleted immediately. To delete a resource pool:

* In the MAAS 3.4 UI, choose *Organisation* > *Pools* > *trash can* > *Delete*.

* With the UI in all other versions of MAAS, choose *Resource* > *(trash can)* > *Delete*.

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE resource-pool delete $RESOURCE_POOL_ID
```

## Add a machine to a pool

To add a machine to a resource pool:

* In the MAAS 3.4 UI, choose *Machines* > (machine) > *Categorise* > *Set pool* > *Select pool* > *Resource pool* > *Set pool*.

* With the UI in all other versions of MAAS, choose *Machines* > (machine) > *Configuration* (resource pool) > *Save changes*.

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE machine update $SYSTEM_ID pool=$POOL_NAME
```
    
## Remove a machine from a pool

To remove a machine from a resource pool:

* In the MAAS 3.4 UI, choose *Machines* > (machine) > *Categorise* > *Set pool* > *Select pool* > *Resource pool* >"default" > *Set pool*.

* With the UI in all other versions of MAAS, choose *Machines* > (machine) > *Configuration* > "default" > *Save changes*.

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE machine update $SYSTEM_ID pool="default"
```

## Add a VM host to a pool

To add a VM host to a resource pool:

* In the MAAS 3.4 UI, choose *KVM* > *LXD* > (VM host) >  *KVM host settings* > *Resource pool* > *Save changes*.

With the UI in all other versions of MAAS, you can add a VM host to a resource pool when you create a new VM host, or you can edit the VM host's configuration:

![image](https://assets.ubuntu.com/v1/84a89952-nodes-resource-pools__2.5_pod_to_pool.png)

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE machine update $SYSTEM_ID pool=$POOL_NAME
```

## Remove a VM host from a pool

To remove a VM host from a resource pool:

* In the MAAS 3.4 UI, choose *KVM* > *LXD* > (VM host) > *KVM host settings* > *Resource pool* > "default" > *Save changes*.

* With the UI in all other versions of MAAS, edit the VM host's configuration and assign it to the "default" resource pool:

![image](https://assets.ubuntu.com/v1/84a89952-nodes-resource-pools__2.5_pod_to_pool.png)

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE machine update $SYSTEM_ID pool="default"
```

## List resource pools (CLI)

Via the MAAS CLI, use the following command:

```nohighlight
maas $PROFILE resource-pools read
```

## List a single pool

Via the MAAS CLI, use the following command:

```nohighlight
maas $PROFILE resource-pool read $RESOURCE_POOL_ID
```

## Update a pool

Via the MAAS CLI, use the following command:

```nohighlight
maas $PROFILE resource-pool update $RESOURCE_POOL_ID name=newname description="A new description."
```

> The `description` field is optional.
