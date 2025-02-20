> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/manage-machines" target = "_blank">Let us know.</a>*

## **Find machines**  

### **Discover active machines**  
MAAS detects devices via network traffic.  

**UI**  
*Networking > Network discovery*  

**CLI**  
```bash
maas $PROFILE discoveries read
```

### **Find a machine’s ID**  
Everything in MAAS revolves around the **system ID**. Get it:  

**UI**  
*Machines > [machine]* (Check browser URL: `...machine/<SYSTEM_ID>/summary`)  

**CLI**  
```bash
maas admin machines read | jq -r '(["HOSTNAME","SYSID"] | (., map(length*"-"))),(.[] | [.hostname, .system_id]) | @tsv' | column -t
```

### **List machines**  
**UI**  
*Machines* (View list)  

**CLI**  
```bash
maas $PROFILE machines read | jq -r '(["HOSTNAME","SYSID","STATUS"] | join(","))'
```

### **Search for machines**  
Use MAAS search syntax to find specific machines.  

**UI**  
*Hardware > Machines > [Search bar]* and enter a search term; MAAS updates the list dynamically.  

For exact matches, prefix the value with `=`; for partial matches, omit it; and for negation, use `!`:  
```no-highlight
Exact: pod:=able-cattle
Partial: pod:able,cattle
Negated: pod:!cattle
```

**CLI**  
```bash
maas $PROFILE machines read | jq -r '(["HOSTNAME","SYSID","STATUS"] | join(","))'
```

### **Filter machines by parameters**  
**UI**  
*Hardware > Machines > Filters dropdown > [Select parameters]*  

MAAS builds the search term dynamically and updates the list. You can copy and save these terms for reuse.

## **Add & configure machines**  

### **Add a machine**  
Provide architecture, MAC address, power type, and parameters.  

**UI**  
*Machines > Add hardware*  

**CLI**  
```bash
maas $PROFILE machines create architecture=$ARCH mac_addresses=$MAC_ADDRESS \
  power_type=$POWER_TYPE power_parameters_power_id=$POWER_ID \
  power_parameters_power_address=$POWER_ADDRESS power_parameters_power_pass=$POWER_PASSWORD
```

### **Clone a machine**  
**UI**  
*Machines > [machine] > Take action > Clone*  

**CLI**  
```bash
maas $PROFILE machine clone $SOURCE_SYSTEM_ID new_hostname=$NEW_HOSTNAME
```

### **Set power type**  
Without this, **MAAS can’t control the machine.**  

**UI**  
*Machines > [machine] > Configuration > Power > Edit*  

**CLI**  
```bash
maas $PROFILE machine update $SYSTEM_ID power_type="$POWER_TYPE"
```

## **Control machine power**  

### **Turn on**  
**UI**  
*Machines > [machine] > Take action > Power on*  

**CLI**  
```bash
maas $PROFILE machine start $SYSTEM_ID
```

### **Turn off** 
**UI**  
*Machines > [machine] > Take action > Power off*  

**CLI**  
```bash
maas $PROFILE machine stop $SYSTEM_ID
```

### **Soft power-Off**  
```bash
maas $PROFILE machine stop $SYSTEM_ID force=false
```

## **Commission & test machines**  

### **Commission a machine**  
**Required before deployment.**  

**UI**  
*Machines > [machine] > Take action > Commission*  

**CLI**  
```bash
maas $PROFILE machine commission $SYSTEM_ID
```

### Run tests
**UI**  
*Machines > [machine] > Take action > Test*  

**CLI**  
```bash
maas $PROFILE machine test $SYSTEM_ID tests=cpu,storage
```

### **View test results**  
**UI**  
*Machines > [machine] > Test results*  

**CLI**  
```bash
maas $PROFILE machine read $SYSTEM_ID | jq '.test_results'
```

### **Override failed tests**  
**UI**  
*Machines > [machine] > Take action > Override test results*  

**CLI**  
```bash
maas $PROFILE machine set-test-result $SYSTEM_ID result=passed
```

## **Deploy machines**  

### **Allocate a machine**  
**Locks ownership to the user who allocates it.**  

**UI**  
*Machines > [machine] > Take action > Allocate*  

**CLI**  
```bash
maas $PROFILE machines allocate system_id=$SYSTEM_ID
```

### **Deploy a machine**  
**UI**  
*Machines > [machine] > Take action > Deploy*  

**CLI**  
```bash
maas $PROFILE machine deploy $SYSTEM_ID
```

### **Deploy as a VM host**  
**UI**  
*Machines > [machine] > Take action > Deploy > Install KVM*  

**CLI**  
```bash
maas $PROFILE machine deploy $SYSTEM_ID install_kvm=True
```

### **Deploy with cloud-init config**  
**UI**  
*Machines > [machine] > Take action > Deploy > Configuration options*  

**CLI**  
```bash
maas $PROFILE machine deploy $SYSTEM_ID cloud_init_userdata="$(cat cloud-init.yaml)"
```

## **Configure machine settings**  

### **Set kernel version**  
**System-wide default:**  
**UI**  
*Settings > Configuration > Commissioning > Default minimum kernel version*  

**CLI**  
```bash
maas $PROFILE maas set-config name=default_min_hwe_kernel value=$KERNEL
```

**Per-machine kernel:**  
**UI**  
*Machines > [machine] > Configuration > Edit > Minimum kernel*  

**CLI**  
```bash
maas $PROFILE machine update $SYSTEM_ID min_hwe_kernel=$HWE_KERNEL
```

**Deploy with a specific kernel:**  
**UI**  
*Machines > [machine] > Take action > Deploy > Choose kernel*  

**CLI**  
```bash
maas $PROFILE machine deploy $SYSTEM_ID distro_series=$SERIES hwe_kernel=$KERNEL
```

### **Set boot options**  
**System-wide default:**  
**UI**  
*Settings > Kernel parameters*  

**CLI**  
```bash
maas $PROFILE maas set-config name=kernel_opts value='$KERNEL_OPTIONS'
```

### **Configure storage layout**  
**Default layout for all machines:**  
**UI**  
*Settings > Storage > Default layout*  

**CLI**  
```bash
maas $PROFILE maas set-config name=default_storage_layout value=$LAYOUT_TYPE
```

**Per-machine layout:**  
**UI**  
*Machines > [machine] > Storage > Edit layout*  

**CLI**  
```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=$LAYOUT_TYPE
```

## **Rescue & recovery**  

### **Enter rescue mode**  
**UI**  
*Machines > [machine] > Take action > Enter rescue mode*  

**CLI**  
```bash
maas $PROFILE machine enter-rescue-mode $SYSTEM_ID
```

### **SSH into a machine**  
```bash
ssh ubuntu@$MACHINE_IP
```

### **Exit rescue mode**  
**UI**  
*Machines > [machine] > Take action > Exit rescue mode*  

**CLI**  
```bash
maas $PROFILE machine exit-rescue-mode $SYSTEM_ID
```

### **Mark a machine as broken**  
**UI**  
*Machines > [machine] > Take action > Mark broken*  

**CLI**  
```bash
maas $PROFILE machines mark-broken $SYSTEM_ID
```

### **Mark a machine as fixed**  
**UI**  
*Machines > [machine] > Take action > Mark fixed*  

**CLI**  
```bash
maas $PROFILE machines mark-fixed $SYSTEM_ID
```

## **Release or remove machines**  

### **Release a machine**  
**UI**  
*Machines > [machine] > Take action > Release*  

**CLI**  
```bash
maas $PROFILE machines release $SYSTEM_ID
```

### **Erase disks on release**  
**UI**  
*Machines > [machine] > Take action > Release > Enable disk erasure options*  

**CLI**  
```bash
maas $PROFILE machine release $SYSTEM_ID erase=true secure_erase=true quick_erase=true
```

### **Delete a machine**  
**UI**  
*Machines > [machine] > Take action > Delete*  

**CLI**  
```bash
maas $PROFILE machine delete $SYSTEM_ID
```

### **Force delete a stuck machine**  
```bash
maas $PROFILE machine delete $SYSTEM_ID force=true
```

## **Verify everything**  

### **Check all machines**  
**UI**  
*Machines* (View list or search)  

**CLI**  
```bash
maas $PROFILE machines read | jq -r '.[].hostname'
```
