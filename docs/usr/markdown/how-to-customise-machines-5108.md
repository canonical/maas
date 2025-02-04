**Report Issues**  
Errors or typos? Missing topics? [Let us know](https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/customising-machine-specifications).

---

MAAS allows machine customization before provisioning using Curtin or cloud-init.

## Curtin pre-seeding

You can customize Curtin via the `curtin_userdata` template or by adding a custom file. Curtin supports `early` and `late` hooks for pre/post-installation customization.

- **Early Command Example:**
  ```yaml
  early_commands:
    signal: ["wget", "--no-proxy", "http://example.com/", "--post-data", "system_id=&signal=starting_install", "-O", "/dev/null"]
  ```
- **Late Commands Example:**
  ```yaml
  late_commands:
    add_repo: ["curtin", "in-target", "--", "add-apt-repository", "-y", "ppa:my/ppa"]
    custom: ["curtin", "in-target", "--", "sh", "-c", "/bin/echo -en 'Installed ' > /tmp/maas_system_id"]
  ```

## Cloud-init pre-seeding

To customize cloud-init:

- **MAAS 3.4+ UI:**  
  *Machines* > machine > *Actions* > *Deploy* > *Cloud-init user-data* > enter customizations > *Start deployment*.
  
- **Other versions UI:**  
  *Take action* > *Deploy* > <release> > *Cloud-init user-data* > enter customizations > *Start deployment*.

- **CLI:**
  ```bash
  maas $PROFILE machine deploy $SYSTEM_ID user_data=<base-64-encoded-script>
  ```

## Set default minimum kernel

To set the default kernel for all machines:

- **MAAS 3.4+ UI:**  
  *Settings* > *Configuration* > *Commissioning* > *Default minimum kernel version* > *Save*.
  
- **Other versions UI:**  
  *Settings* > *General* > *Default minimum kernel version* > *Save*.

- **CLI:**
  ```bash
  maas $PROFILE maas set-config name=default_min_hwe_kernel value=$KERNEL
  ```

## Set minimum kernel per machine

To set a minimum deployment kernel for a specific machine:

- **MAAS UI:**  
  *Machines* > machine > *Configuration* > *Edit* > *Minimum kernel*.

- **CLI:**
  ```bash
  maas $PROFILE machine update $SYSTEM_ID min_hwe_kernel=$HWE_KERNEL
  ```

## Set specific kernel during deployment

To set a kernel during deployment:

- **MAAS UI:**  
  *Machines* > machine > *Take action* > *Deploy* > choose kernel > *Deploy machine*.

- **CLI:**
  ```bash
  maas $PROFILE machine deploy $SYSTEM_ID distro_series=$SERIES hwe_kernel=$KERNEL
  ```

## Set global kernel boot options

To set global kernel boot options:

- **MAAS 3.4+ UI:**  
  *Settings* > *Kernel parameters* > enter options > *Save*.

- **Other versions UI:**  
  *Settings* > *General* > enter options > *Save*.

- **CLI:**
  ```bash
  maas $PROFILE maas set-config name=kernel_opts value='$KERNEL_OPTIONS'
  ```

## Kernel option tags

To create a tag with kernel options:

```bash
maas $PROFILE tags create name='$TAG_NAME' comment='$TAG_COMMENT' kernel_opts='$KERNEL_OPTIONS'
```

View tags:
```bash
maas admin tags read | jq -r '(["tag_name","tag_comment","kernel_options"] |(.,map(length*"-"))),(.[]|[.name,.comment,.kernel_opts]) | @tsv' | column -t
```

## Enable hardware sync (MAAS 3.2+)

To enable hardware sync:

- **MAAS 3.4+ UI:**  
  *Machines* > machine > *Actions* > *Deploy* > *Periodically sync hardware* > *Start deployment*.

- **Other versions UI:**  
  *Take action* > *Deploy* > *Periodically sync hardware* > *Start deployment*.

- **CLI:**
  ```bash
  maas $PROFILE machine deploy $SYSTEM_ID osystem=$OSYSTEM distro_series=$VERSION enable_hw_sync=true
  ```

## View Hardware Sync Updates

View updates in the MAAS UI or CLI:
```bash
maas $PROFILE machine read $SYSTEM_ID
```

## Configure Hardware Sync Interval

Configure the sync interval in [MAAS settings](/t/how-to-change-maas-3-4-settings/6347).

## Set default layout

To set the default storage layout for all machines:

- **MAAS UI**:  
  1. *Settings* > *Storage* > choose default layout.  
  2.   Enable *Erase machines' disks prior to releasing* to force disk erasure.

- **CLI**:
  ```bash
  maas $PROFILE maas set-config name=default_storage_layout value=$LAYOUT_TYPE
  ```

  Example for setting layout to flat:
  ```bash
  maas $PROFILE maas set-config name=default_storage_layout value=flat
  ```

## Set per-machine layout

Set a storage layout for a 'Ready' machine:

```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=$LAYOUT_TYPE [$OPTIONS]
```

Example with LVM layout:
```bash
maas $PROFILE machine set-storage-layout $SYSTEM_ID storage_layout=lvm lv_size=5368709120
```

## Erase disks

To erase a disk when releasing a machine:

- Use `machine release` (singular) instead of `machines release` (plural).

Example:
```bash
maas $PROFILE machine release $SYSTEM_ID comment="some comment" erase=true [secure_erase=true || quick_erase=true]
```

- Secure erasure uses the drive's secure erase feature, if available.
- Quick erasure wipes 2MB at the start and end of the disk. Not secure but faster.
- If no options are specified, the disk will be overwritten with null bytes (slow).

## Set conditional erasure

To perform secure erasure if available, or quick erasure otherwise:

```bash
maas $PROFILE machine release $SYSTEM_ID comment="some comment" erase=true secure_erase=true quick_erase=true
```