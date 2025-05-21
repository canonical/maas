Commissioning profiles machine hardware (vendor, BIOS, network, CPU, storage, USB/PCI) to tailor deployment. A commissioning failure is low-stakes -- it prevents deployment, avoiding errors. Successful commissioning tests the hardware and sets the machine to "Ready," meanin. successful deployment is likely.

MAAS commissions a machine like this:

1. MAAS uses the BMC to power-on the machine.
2. The machine negotiates an IP address from the MAAS-provided DHCP server.
3. The machine boots an ephemeral Ubuntu LTS image received over TFTP.
4. `cloud-init` sets up SSH keys and NTP.
5. `cloud-init` runs built-in and custom commissioning scripts.
6. The machine shuts down unless configured to remain on after commissioning.

Administrators can specify other ephemeral boot images. The region controller tracks and reports commissioning status.

## Built-in commissioning scripts 

MAAS extracts six built-in commissioning scripts from the MAAS database and runs them in parallel:

- **maas-support-info:** gathers information that helps to identify and characterize the machine for debugging purposes. 

- **maas-lshw:** pulls BIOS and vendor info, and generates user-defined tags for later use.

- **maas-list-modaliases:** identifies the available hardware modules. 

- **maas-get-fruid-api-data:** gathers information for the Facebook wedge power type. 

- **maas-serial-ports:** finds the available serial ports. 

- **maas-capture-lldp:** gathers LLDP network information for logging. 

MAAS extracts four additional scripts from the database and runs them in alphabetical order:

- **20-maas-01-install-lldpd:** installs the link layer discovery protocol (LLDP) daemon to capture networking information. 

- **20-maas-02-dhcp-unconfigured-ifaces:** PXE comes online during boot; this script identifies other attached networks.

- **50-maas-01-commissioning:** gathers information on machine resources, such as storage, network devices, CPU, RAM, and attached USB and PCI devices. Also recognizes virtual machines.

- **maas-kernel-cmdline:** update the boot devices to use the correct boot interface.

Commissioning also:

- Runs user-supplied scripts as root.

- Runs test scripts.

- Configures the machine's BMC by writing power credentials.

Note that commissioning runs only on machines that have a *New* status.

## Optional parameters for built-in scripts

Change how commissioning runs with the following options:

- **`enable_ssh`**: Optional integer to enable SSH for the commissioning environment using the user's SSH key(s). '1' == True, '0' == False. Roughly equivalent to the *Allow SSH access and prevent machine powering off* option in the web UI.

- **`skip_bmc_config`**: Optional integer to skip re-configuration of the BMC for IPMI based machines. '1' == True, '0' == False.

- **`skip_networking`**: Optional integer to skip re-configuring the networking on the machine after the commissioning has completed. '1' == True, '0' == False. Roughly equivalent to *Retain network configuration* in the web UI.

- **`skip_storage`**: Optional integer to skip re-configuring the storage on the machine after the commissioning has completed. '1' == True, '0' == False. Roughly equivalent to *Retain storage configuration* in the web UI.

- **`commissioning_scripts`**: Optional string. A comma separated list of commissioning script names and tags to be run. By default all custom commissioning scripts are run. Built-in commissioning scripts always run. Selecting `update_firmware` or `configure_hba` will run firmware updates or configure HBA's on matching machines.

- **`testing_scripts`**: Optional string. A comma separated list of testing script names and tags to be run. By default all tests tagged `commissioning` will be run. Set to `none` to disable running tests.

- **`parameters`**: Optional string. Scripts selected to run can define their own parameters. These parameters are passed using the parameter name. A parameter can have the script name prepended to have that parameter only apply to that specific script.

## Commissioning logs 

MAAS logs timestamped records of commissioning events for every machine. If commissioning fails, check the logs first.

## Debugging scripts 

Scripts log full results regardless of success or failure. For more details, choose the option to leave the machine on after commissioning. You can then connect to the machine and examine its logs. 

If you've added your [SSH key](https://maas.io/docs/sshkey) to MAAS, you may connect with SSH to the machine's IP with a username of `ubuntu`. Enter `sudo -i` to get root access.

## Automatic selection 

When selecting multiple machines, scripts declaring the `for_hardware` field will run only on machines with matching hardware. To automatically run a script when *Update firmware* or *Configure HBA* is selected, you must tag the script appropriately. Command-line scripts that specify `for_hardware` also run only on matching hardware.

## NUMA and SR-IOV 

MAAS assigns machines to a single NUMA node by default to avoid latency. Match VM boundaries to NUMA boundaries for best results. Specify a node index for interfaces and physical block devices. 

MAAS reports NUMA node details, such as the index, node count, CPU cores, memory, NICs, and node spaces. You can filter machines by CPU cores, memory, subnet, VLAN, fabric, space, storage, and RAID.

## Disabling boot methods 

You can disable individual boot methods with the MAAS CLI on a VLAN/subnet basis. MAAS-provided DHCP will not respond to the associated boot architecture code for disabled methods. External DHCP servers must be configured manually.

## Interpreting scripts 

Scripts write results to a YAML file in `RESULT_PATH` before exiting. The YAML file has two fields:

1. `result`: The completion status of the script: `passed`, `failed`, `degraded`, or `skipped`. Some scripts return `0` or non-zero values for "failed" and "passed," respectively.

2. `results`: A dictionary of results, presented as strings.

Script return results specified by metadata fields:

1. `title` - The title for the result, used in the UI.

2. `description` - The description of the field used as a tool-tip in the UI.

Here is an example of "degrade detection":

```nohighlight
!/usr/bin/env python3

 --- Start MAAS 1.0 script metadata ---
 name: example
 results:
. memspeed:
.  title: Memory Speed
.  description: Bandwidth speed of memory while performing random read writes
 --- End MAAS 1.0 script metadata ---

import os
import yaml

memspeed = some_test()

print('Memspeed: %s' % memspeed)
results = {
. 'results': {
. . 'memspeed': memspeed,
. }
}
if memspeed < 100:
. print('WARN: Memory test passed but performance is low!')
. results['status'] = 'degraded'

result_path = os.environ.get("RESULT_PATH")
if result_path is not None:
. with open(result_path, 'w') as results_file:
. . yaml.safe_dump(results, results_file)
```

## Tagging scripts 

Tags make scripts easier to manage. These tags group together commissioning and testing scripts:

```nohighlight
maas $PROFILE node-script add-tag $SCRIPT_NAME tag=$TAG
maas $PROFILE node-script remove-tag $SCRIPT_NAME tag=$TAG
```

MAAS runs all commissioning scripts by default, but you can select custom commissioning scripts by name or tag:

```nohighlight
maas $PROFILE machine commission \
commissioning_scripts=$SCRIPT_NAME,$SCRIPT_TAG
```

You can also select testing scripts by name or tag:

```nohighlight
maas $PROFILE machine commission \
testing_scripts=$SCRIPT_NAME,$SCRIPT_TAG
```

Any testing scripts tagged with `commissioning` will also run during commissioning.

## Testing hardware 

You can test machine hardware using any available Linux utility. You can create your own testing scripts and read their logs. MAAS tests machines that that are **Ready**, **Broken**, or **Deployed**. If the hardware tests fail, you can't deploy the machine. Testing scripts don't always work with virtual machines.

## Interpreting logs 

You can also examine log details on any particular tests or just review the raw log output. Help interpreting these logs can be found under the [Logging](https://maas.io/docs/about-maas-logging) section of this documentation.

## Testing networks 

MAAS can test networks and links, including connection status and link speeds. You can test Internet connectivity against a user-provided list of URLs or IP addresses. Bonded NICS are separated during this testing to check each side of a dual interface. You can also provide custom scxripts with no restrictions.

## Delayed NW config 

Once commissioned, you can configure the machine's network interface(s). Specifically, when a machine's status is either "Ready" or "Broken", interfaces can be added/removed, attached to a fabric or subnet, and provided an IP assignment mode. Tags can also be assigned to specific network interfaces.

