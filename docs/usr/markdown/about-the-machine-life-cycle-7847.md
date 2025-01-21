> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/machines" target = "_blank">Let us know.</a>*

Understanding a machine's life-cycle is key to leveraging MAAS effectively.  Everything that happens to a machine under MAAS control conforms to a specific life-cycle.  All MAAS machines are in a named state, or in transition between states.  Most of these transitions are user-controlled.  Only the "failure" state is reached under the direction of MAAS, when a user's request for certain state changes can't be successfully completed.

## Machine states 

In general, the various states and transitions can be summarised in a diagram:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/b/bd9e5e225ffee4b2e88104e5bbd363dd2ef61a88.jpeg)

The central state flow at the bottom of the diagram is the "standard" life-cycle.  If all goes well, you won't have to deviate much from this flow:

- Machines start as servers in your environment, attached to a network or subnet that MAAS can reach and manage.  If those machines are configured to netboot, MAAS can discover them and enlist them, assigning a status of "NEW". By definition, NEW machines are: (2) enabled to network boot, and (2) on a subnet accessible to MAAS. 

- Once you've pared the list to machines that you want MAAS to control, you can choose to commission them.  You can select any machine that is marked "NEW" and tell MAAS to commission it, or, if you add machine manually, MAAS will automatically commission it.  Commissioning PXE boots the machine and loads an ephemeral version of the Ubuntu operating system into the machine's RAM.  MAAS then uses that OS to scan the machine to determine its hardware configuration: CPUs, RAM, storage layouts, PCI and USB devices, and so forth.  Commissioning can be customised -- more on that in a later section.  If a machine fails to properly commission, either because of a commissioning error, or because the commissioning process timed out, that machine enters a "FAILED" state.
  
- MAAS next tests the machine to make sure it's working properly. These basic tests just assure that the discovered hardware works as expected.  Testing can also be customised, if you wish.  Machines that don't pass these tests are moved to a "FAILED" state.

- Having tested it, MAAS then places that machine in the "READY" state, meaning that MAAS should be able to deploy it, based on the gathered hardware information.

- Before you deploy a machine, you should allocate it.  This step essentially involves taking ownership of the machine, so that no other users can deploy it.

- Having allocated a machine, you can deploy it.  When deploying, MAAS again loads an ephemeral Ubuntu OS onto the machine, uses `curtin` to configure the hardware in the way you've specified, and then loads and boots the OS image you've requested.  Deployment also runs some `cloud-init` steps to finish machine configuration, before leaving it up and ready for use.  

Once deployed, there are a couple of minor state changes you can effect without releasing the machine:

- You can lock a machine, if desired, to provide a little extra insurance that it won't accidentally be changed by you -- or anyone.

- Depending upon the machine's duty cycle, you can also power it on, power it off, or even power-cycle it (to effect a reboot, for example).

Note that these minor state changes are not shown in the diagram above.  There are also some exceptional states you can command:

- For any machine that is ready, allocated, or deployed, you can cycle it through a battery of tests at any time.  Be aware, of course, that testing causes the machine to be unavailable for normal use for the duration of the text cycle.

- Machines that are ready, allocated, or deployed can also be placed in "rescue mode".  Essentially, rescue mode is the same as walking to a malfunctioning or mis-configured machine, taking it off the network, and fixing whatever may be wrong with it -- except that you're doing so via SSH, or by running tests from MAAS, rather than standing in front of the machine.  Machines in rescue mode can't enter normal life cycle states until you remove them from rescue mode.  You can, of course, delete them, modify their parameters (tags, zone, and so on), power them off, and mark them broken.  Rescue mode is like a remote repair state that you can control from wherever you are.

- Machines that are allocated or deployed can also be marked broken.  A broken machine powers off by default.  You can still power it on, delete it, or enter rescue mode, but you can't log into it via SSH.  This state is intended for machines that experience catastrophic hardware or software failures and need direct repairs.

There is one more state that a machine can get into: "failed".  This state is entered when commissioning, allocation, or deployment are not successful.  Getting out of a failed state means figuring out what went wrong, correcting it, and retrying the failed operation.  For example, when a machine fails, you can try and commission it again, hopefully after you've found the bug in your custom commissioning script that's causing it to fail (for instance).

Now that we have a solid overview of the life-cycle, let's break down some of these states and transitions in greater detail.

## Enlistment 

MAAS is built to manage machines, including the operating systems on those machines. Enlistment and commissioning are features that make it easier to start managing a machine -- as long as that machine has been configured to netboot. Enlistment enables users to simply connect a machine, configure the firmware properly, and power it on so that MAAS can find it and add it.

Enlistment happens when MAAS starts; it reaches out on connected subnets to locate any nodes -- that is, devices and machines -- that reside on those subnets. MAAS finds a machine that's configured to netboot (e.g., via PXE), boots that machine into Ubuntu, and then sends cloud-init user data which runs standard (i.e., built-in) commissioning scripts. The machine actually adds itself over the MAAS API, and then requests permission to send commissioning data.

Since MAAS doesn't know whether you might intend to actually include these discovered machines in your cloud configuration, it won't automatically take them over, but it will read them to get an idea how they're set up. MAAS then presents these machines to you with a MAAS state of "New." This allows you to examine them and decide whether or not you want MAAS to manage them.

When you configure a machine to netboot -- and turn it on while connected to the network -- MAAS will enlist it, giving it a status of "New."  You can also add a machine manually. In either case, the next step is *commissioning*, which boots the machine into an ephemeral Ubuntu kernel so that resource information can be gathered.  You can also run custom commissioning scripts to meet your specific needs.

## Enlistment details 

When MAAS enlists a machine, it first contacts the DHCP server, so that the machine can be assigned an IP address.  An IP address is necessary to download a kernel and initrd via TFTP, since these functions can't accept domain names.  Once the machine has a bootable kernel, MAAS boots it:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/76f7113545e6950fec60bdeac06cfaf79b14b3ff.jpeg)

Next, initrd mounts a Squashfs image, ephemerally via HTTP, so that cloud-init can execute:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/500f9bd2d070790a4007085705035366bee88a4a.jpeg)

Finally, cloud-init runs enlistment and setup scripts:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/bd87f78c8ee668a22640bf15607c9e3e532d46bb.jpeg)

The enlistment scripts send information about the machine to the region API server, including the architecture, MAC address and other details.  The API server, in turn, stores these details in the database. This information-gathering process is known as [automatic discovery or network discovery](/t/about-maas-networks/5084).

Typically, the next step will be to commission the machine. As an alternative to enlistment, an administrator can add a machine manually. Typically this is done when enlistment doesn't work for some reason. Note that when you manually add a machine, MAAS automatically commissions the machine as soon as you've added it.

After the commissioning process, MAAS places the machine in the ‘Ready’ state. ‘Ready’ is a holding state for machines that are commissioned, waiting to be deployed when needed.


MAAS runs built-in commissioning scripts during the enlistment phase. When you commission a machine, any customised commissioning scripts you add will have access to data collected during enlistment. Follow the link above for more information about commissioning and commission scripts.


## BMC enlistment 

For IPMI machines, you only need to provide IPMI credentials. MAAS automatically discovers the machine and runs enlistment configuration by matching the BMC address.  For non-IPMI machines, you must specify a non-PXE MAC address. MAAS automatically discovers the machine and runs enlistment configuration by matching the non-PXE MAC address.

## Adding machines 

There are two ways to add a machine to MAAS:

1. If you place the machine on a connected network, and the machine is configured to netboot, MAAS will automatically enlist it.

2. If you add a machine manually, MAAS will automatically commission it.  There are also ways to turn off this automatic commissioning, should you desire to do so.

MAAS typically adds a machine via a combination of DHCP, TFTP, and PXE. By now, you should have enabled MAAS to automatically add devices and machines to your environment. This unattended method of adding machines is called enlistment.

Configuring a computer to boot over PXE is done via its BIOS, often referred to as "netboot" or "network boot". Normally, when you add a machine manually, MAAS will immediately attempt to commission the machine. Note that you will need to configure the underlying machine to netboot, or commissioning will fail. MAAS cannot handle this configuration for you.  While the correct method for configuring network boot depends heavily on your server, there are two common elements:

1. The network card on your server must be able to support PXE, i.e., your NIC -- whether independent or integrated on a motherboard -- must have a boot PROM that supports network booting.  You'll need to consult the documentation for the machine in question to determine this. Note that in MAAS versions before 2.5, you are required to provide the MAC address of the PXE interface when adding a new machine manually.

2. You usually have to interrupt the boot process and enter the BIOS/UEFI menu to configure the network card's PXE stack.  Again, you may need to consult your machine's documentation to pin down this step.

Additional steps will vary widely by machine type and architecture.

Regardless of how MAAS adds a machine, there are no special requirements for the underlying machine itself, other than being able to netboot. In particular, there is no need to install an operating system on it.

## Cloning (3.1++)

MAAS v3.1 and higher provides the ability to quickly clone or copy configuration from one machine to one or more machines, via the MAAS UI, providing convenient access to an existing API feature.. This is a step towards machine profile templating work. 

Creating a machine profile is a repetitive task. Based on the responses to our survey -- and multiple forum posts, we have learned that most users create multiple machines of the same configuration in batches. Some users create a machine profile template and loop them through the API, while some create a script to interface with the CLI. However, there is no easy way to do this in the UI except by going through each machine and configuring them individually.   

MAAS API already has the cloning functionality, but it was never exposed in the UI. Hence, users may not know that this API feature exists, nor is there any current documentation about how to use this feature.  Although the current cloning API feature does not solve all machine profile templating problems, it is a great place for us to start moving in the direction of machine templates.

## Faithful copies 

As a MAAS user -- API or UI -- you may want to copy the configuration of a given machine and apply it to multiple existing machines. Assuming that at least one machine is already set to the desired configuration, you should be able to apply these same settings to a list of destination machines.  This means that a user should be able to:

- select the source machine to copy from.
- validate that the source machine exists.
- select at least 1 destination machine.
- validate that the destination machine(s) exist.
- edit the source machine or destination machines, if needed.
- know at all times which machines are affected.
- see the cloned machines when cloning is successful, or
- get clear failure information, if cloning fails. 

## What to copy? 

As a MAAS user, you will likely want to select whether storage, network, or both configurations should be cloned. The cloning API allows users to choose interfaces and storage separately.  Thus, this new feature should allow the user to:

- clone only the interface (network) configuration.
- clone only the storage configuration.
- clone both configurations.

## Restrictions 

In order for cloning to succeed, a few restrictions must be met:

- The destination interface names must be the same source.
- The destination drive must be equal to or larger than the source drive.
- For static IPs, a new IP will be allocated to the interface on the destination machine

## Adding live machines (3.1++)

In general, when adding a machine to MAAS, it network boots the machine into an ephemeral environment to collect hardware information about the machine. While this is not a destructive action, it doesn’t work if you have machines that are already running a workload.

For one, you might not be able to disrupt the workload in order to network boot it. But also, the machine would be marked as Ready, which is incorrect.

When adding a machine, you may specify that the machine is already deployed. In that case, it won’t be going through the normal commissioning process and will be marked as being deployed.

Such machines lack hardware information. In order to update the information, a script is provided to run a subset of the commissioning scripts and send them back to MAAS.

Because already-deployed machines were not deployed by MAAS, most of the standard MAAS commands will not affect the machine and may, at times, return some odd results.  This is not errant behaviour; the goal of enlisting deployed machines is to avoid disturbing their workload.