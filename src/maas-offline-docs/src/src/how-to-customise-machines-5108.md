> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/customising-machine-specifications" target = "_blank">Let us know.</a>*

MAAS allows you to customize machines before you provision them, using curtin or cloud-init. 

## Pre-seed curtin

You can customise the Curtin installation by either editing the existing `curtin_userdata` template or by adding a custom file as described above. For a flowchart, showing where Curtin and pre-seeding fits into the deployment picture, see [About deploying machines](/t/about-deploying-machines/7901).

Curtin provides hooks to execute custom code before and after installation takes place. These hooks are named `early` and `late` respectively, and they can both be overridden to execute the Curtin configuration in the ephemeral environment. Additionally, the `late` hook can be used to execute a configuration for a machine being installed, a state known as in-target.

Curtin commands look like this:

```nohighlight
    foo: ["command", "--command-arg", "command-arg-value"]
```

Each component of the given command makes up an item in an array. Note, however, that the following won't work:

```nohighlight
    foo: ["sh", "-c", "/bin/echo", "foobar"]
```

This syntax won't work because the value of `sh`'s `-c` argument is itself an entire command. The correct way to express this is:

```nohighlight
    foo: ["sh", "-c", "/bin/echo foobar"]
```

The following is an example of an early command that will run before the installation takes place in the ephemeral environment. The command pings an external machine to signal that the installation is about to start:

```nohighlight
early_commands:
  signal: ["wget", "--no-proxy", "http://example.com/", "--post-data", "system_id=&signal=starting_install", "-O", "/dev/null"]
```

The following is an example of two late commands that run after installation is complete. Both run in-target, on the machine being installed.

The first command adds a PPA to the machine. The second command creates a file containing the machine’s system ID:

```nohighlight
late_commands:
  add_repo: ["curtin", "in-target", "--", "add-apt-repository", "-y", "ppa:my/ppa"]
  custom: ["curtin", "in-target", "--", "sh", "-c", "/bin/echo -en 'Installed ' > /tmp/maas_system_id"]
```

## Pre-seed cloud-init

For a flowchart, showing where cloud-init fits into the deployment picture, see [About deploying machines](/t/about-deploying-machines/7901).

To customise cloud-init: 

* In the MAAS 3.4 UI, select *Machines* > machine > *Actions* > *Deploy* > *Cloud-init user-data...* > enter cloud-init customisations > *Start deployment for machine*.

* With the UI for all other MAAS versions, select a machine > *Take action* > *Deploy* > <viable release> > *Cloud-init user-data..." > enter desired cloud-init script > *Start deployment for machine*.

* Via the CLI, use the following command:

```nohighlight
	maas $PROFILE machine deploy $SYSTEM_ID user_data=<base-64-encoded-script>
```
	
    The three replaceable parameters shown above decode to:

    1.  `$PROFILE`: Your MAAS login. E.g. `admin`
    2.  `$SYSTEM_ID`: The machine's system ID (see example below)
    3.  `<base-64-encoded-script>`: A base-64 encoded copy of your cloud-init script. See below for an example.

## Set the default minimum kernel

To set the default minimum enlistment and commissioning kernel for all machines:

* In the MAAS 3.4 UI, select *Settings* > *Configuration* > *Commissioning* > *Default minimum kernel version* (dropdown) > *Save*.

* With the UI for all other MAAS versions, select *Settings* > *General* > *Default minimum kernel version* (dropdown) > *Save*.

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE maas set-config name=default_min_hwe_kernel value=$KERNEL
```
    
    For example, to set it to the 16.04 GA kernel:
    
```nohighlight
    maas $PROFILE maas set-config name=default_min_hwe_kernel value=ga-16.04
```
    
Note that the command option `default_min_hwe_kernel` appears to apply to only HWE kernels but this is not the case.
    
## Set minimum deployment kernel for one machine

To set the minimum deployment kernel on a machine basis: 

* In the MAAS UI, set *Machines* > machine > *Configuration* > *Edit* > *Minimum kernel*.

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE machine update $SYSTEM_ID min_hwe_kernel=$HWE_KERNEL
```
    
    For example, to set it to the HWE 16.04 kernel:
    
```nohighlight
    maas $PROFILE machine update $SYSTEM_ID min_hwe_kernel=hwe-16.04
```
    
## Set a specific kernel during machine deployment

To set a specific kernel during deployment:

* In the MAAS UI, select *Machines* > machine > *Take action* > *Deploy* > choose a kernel > *Deploy machine*.
MAAS verifies that the specified kernel is available for the given Ubuntu release (series) before deploying the machine.

* Via the MAAS CLI, use the following command:

```nohighlight
    maas $PROFILE machine deploy $SYSTEM_ID distro_series=$SERIES hwe_kernel=$KERNEL
```
    
The operation will fail if the kernel specified by `hwe_kernel` is older than the kernel (possibly) given by `default_min_hwe_kernel`. Similarly, it will not work if the kernel is not available for the given distro series (such as 'hwe-16.10' for 'xenial').

## Set global kernel boot options

To set global kernel boot options:

* In the MAAS 3.4 UI, select *Settings* > *Kernel parameters* > enter the *Global boot parameters always passed to the kernel* > *Save*.

* With the UI for all other versions of MAAS, select *Settings* > *General* > *Global Kernel Parameters* section > enter options > *Save*.

* Via the MAAS CLI, you can set kernel boot options and apply them to all machines with the following command:

```nohighlight
    maas $PROFILE maas set-config name=kernel_opts value='$KERNEL_OPTIONS'
```

## Kernel option tags (CLI)

You can create tags with embedded kernel boot options. When you apply such tags to a machine, those kernel boot options will be applied to that machine on the next deployment.

To create a tag with embedded kernel boot options, use the following command:

```nohighlight
maas $PROFILE tags create name='$TAG_NAME' \
    comment='$TAG_COMMENT' kernel_opts='$KERNEL_OPTIONS'
```

For example:

```nohighlight
maas admin tags create name='nomodeset_tag' \
    comment='nomodeset_kernel_option' kernel_opts='nomodeset vga'
```

This command yields the following results:

```nohighlight
Success.
Machine-readable output follows:
{
    "name": "nomodeset_tag",
    "definition": ",
    "comment": "nomodeset_kernel_option",
    "kernel_opts": "nomodeset vga",
    "resource_uri": "/MAAS/api/2.0/tags/nomodeset_tag/"
}
```

You can check your work with a modified form of the listing command:

```nohighlight
maas admin tags read | jq -r \
'(["tag_name","tag_comment","kernel_options"]
|(.,map(length*"-"))),(.[]|[.name,.comment,.kernel_opts]) 
| @tsv' | column -t
```

This should give you results something like this:

```nohighlight
tag_name             tag_comment                  kernel_options                     
--------             -----------                  --------------                     
virtual                                                                              
new_tag              a-new-tag-for-test-purposes                                     
pod-console-logging  console=tty1                 console=ttyS0                      
nomodeset_tag        nomodeset_kernel_option      nomodeset       vga
```

## Enable hardware sync (MAAS 3.2 and higher)

> MAAS hardware sync may leak the MAAS admin API token. You may need to rotate all admin tokens and re-deploy all machines that have hardware sync enabled. To find out whether this is an issue, and how to fix it, see the [troubleshooting instructions](/t/how-to-troubleshoot-common-issues/5333) for this problem.

To enable Hardware sync on a machine:

* In the MAAS 3.4 UI, select *Machines* > machine > *Actions* > *Deploy* > check *Periodically synch hardware* > *Start deployment*.

* With the UI on all other versions of MAAS, select *Machines* > machine > *Take action* > *Deploy* > check *Periodically synch hardware* > *Start deployment*.

* Via the MAAS CLI, deploy the machine from the command line, adding `enable_hw_sync=true`:

```nohighlight
    maas $PROFILE machine deploy $SYSTEM_ID osystem=$OSYSTEM distro_series=$VERSION enable_hw_sync=true
```
    
Once you've enabled hardware sync, any changes you make to the physical device, or to the VM through the VM host, will show up in the appropriate page for the deployed machine as soon as the sync interval has passed.

## View updates from hardware sync

To view updates from hardware sync:

* In MAAS UI, select *Machines* > machine. Any changes to the machine's hardware configuration will be updated on the next sync. The status bar at the bottom will show times for *Last synced* and *Next sync*. Updated BMC configuration and tags can also be viewed on the machine itself.

* Via the MAAS CLI, hardware sync updates the machine’s blockdevice, interface and device sets on a periodic basis. These can be viewed with the CLI command:

```nohighlight
    maas $PROFILE machine read $SYSTEM_ID
```
    
    The timestamps of the last time data was synced and the estimated next time the machine will be synced can be seen in the `last_sync` and `next_sync` fields respectively.

## Configure hardware sync interval

The hardware sync interval is configured globally in [MAAS deployment settings](/t/how-to-change-maas-3-4-settings/6347).