> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/how-to-manage-resource-pools" target = "_blank">Let us know.</a>*

MAAS uses resource pools to group machines and VM hosts for better allocation. New machines default to the **"default"** pool.  

> *Learn more about [Resource pools](https://maas.io/docs/about-resource-pools)*

## Add a resource pool  

**UI:** 
- **MAAS 3.4:** *Organisation* > *Pools* > *Add pool* > Enter *Name* & *Description* > *Save pool*.  
- **Earlier versions:** *Resource* > *Add pool* > Enter *Name* & *Description* > *Add pool*.  

**CLI:**  
```nohighlight
maas $PROFILE resource-pools create name=$NAME description="$DESCRIPTION"
```

## Delete a resource pool  

**UI:**  
- **MAAS 3.4:** *Organisation* > *Pools* > *(trash can)* > *Delete*.  
- **Earlier versions:** *Resource* > *(trash can)* > *Delete*.  

**CLI:**  
```nohighlight
maas $PROFILE resource-pool delete $RESOURCE_POOL_ID
```

## Add a machine to a pool  

**UI:**  
- **MAAS 3.4 forward:** *Machines* > Select machine > *Categorise* > *Set pool* > Select *Resource pool* > *Set pool*.  
- **Earlier versions:** *Machines* > Select machine > *Configuration* > Set *Resource pool* > *Save changes*.  

**CLI:**  
```nohighlight
maas $PROFILE machine update $SYSTEM_ID pool=$POOL_NAME
```

## Remove a machine from a pool  

**UI:**  
- **MAAS 3.4:** Same as "Add a machine to a pool," but select **"default"** as the resource pool.  
- **Earlier versions:** *Machines* > *(machine)* > *Configuration* > Set pool to **"default"** > *Save changes*.  

**CLI:**  
```nohighlight
maas $PROFILE machine update $SYSTEM_ID pool="default"
```

<!--
## Add a VM host to a pool  

**UI:**  
- **MAAS 3.4:** *KVM* > *LXD* > Select VM host > *KVM host settings* > *Resource pool* > *Save changes*.  
- **Earlier versions:** Assign pool during VM host creation or edit VM host settings.  

**CLI:**  
```nohighlight
maas $PROFILE vm-host update $SYSTEM_ID pool=$POOL_NAME
```

## Remove a VM host from a pool  

**UI:**  
- **MAAS 3.4:** Same as "Add a VM host to a pool," but select **"default"** as the resource pool.  
- **Earlier versions:** Edit VM host settings and assign to **"default"**.  

**CLI:**  
```nohighlight
maas $PROFILE vm-host update $SYSTEM_ID pool="default"
```
-->

## List resource pools  

**CLI:**  
```nohighlight
maas $PROFILE resource-pools read
```

## View a single pool  

**CLI:**  
```nohighlight
maas $PROFILE resource-pool read $RESOURCE_POOL_ID
```

## Update a pool  

**CLI:**  
```nohighlight
maas $PROFILE resource-pool update $RESOURCE_POOL_ID name=newname description="A new description."
```

> `description` is optional.  

