> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/overseeing-individual-virtual-machines" target = "_blank">Let us know.</a>*

This page explains how to manage individual virtual machines.

## Add a VM (3.4 UI)

Navigate to *KVM* > VM host name > *Add VM* and fill out the form:

- If you wish, input a *VM name*.

- Choose between *Use any available core(s)* or *Pin VM to specific core(s)*. If choosing the latter, specify core identities.

- Input the amount of *RAM* needed.

- For advanced settings like *Domain*, *Zone*, *Resource pool*, or *Architecture*, click on *Show advanced* and make your modifications.

- Optionally, you can *Define interfaces*.

- Add disks if necessary by selecting *Add disks*.

When done, click *Compose machine* to spawn the VM. 

You'll find the newly composed VM in the *Machines* tab after a brief period, during which it undergoes auto-commissioning. Resources are automatically deducted from the selected VM host.

## Add a VM (3.3-- UI)

From the VM host's details view, select *Take action* > *Compose*. Choose your preferred *Storage pool* and select *Compose machine*.

> When adding multiple disks, the last disk in the list will function as the boot disk.

Your new machine will be auto-commissioned, and its resources will be deducted from the VM host. 

## Delete a VM (UI)

To delete a VM, choose *Machines* > machine > *Take action* > *Delete*.

## Add a VM (CLI)

Creating a basic VM is as simple as running:

```nohighlight
maas $PROFILE vm-host compose $VM_HOST_ID
```

## Specify VM resources (CLI)

You can specify the resources for your VM using the `cores` and `memory` options:

```nohighlight
maas $PROFILE vm-host compose $VM_HOST_ID cores=4 memory=8G
```

## Define VM architecture (CLI)

To define the architecture for your VM, add the `architecture` option:

```nohighlight
maas $PROFILE vm-host compose $VM_HOST_ID architecture=amd64
```

## Set storage parameters (CLI)

Disk and storage configuration can also be defined when you create a VM:

```nohighlight
maas $PROFILE vm-host compose $VM_HOST_ID disks=1:size=20G
```

## Specify interfaces (CLI)

Network interfaces can be specified during VM creation:

```nohighlight
maas $PROFILE vm-host compose $VM_HOST_ID interfaces=0:space=default
```

## Find VM host IDs (CLI)

To find the ID for your VM host, you can use the following command:

```nohighlight
maas $PROFILE vm-hosts read
```

## Delete a VM (CLI)

To delete a VM, execute:

```nohighlight
maas $PROFILE machine delete $SYSTEM_ID
```

## CLI summary

Here's a quick summary of the CLI commands covered:

- **Creating a basic VM**: `maas $PROFILE vm-host compose $VM_HOST_ID`
- **Specifying resources**: `maas $PROFILE vm-host compose $VM_HOST_ID cores=4 memory=8G`
- **Setting architecture**: `maas $PROFILE vm-host compose $VM_HOST_ID architecture=amd64`
- **Adding storage**: `maas $PROFILE vm-host compose $VM_HOST_ID disks=1:size=20G`
- **Defining interfaces**: `maas $PROFILE vm-host compose $VM_HOST_ID interfaces=0:space=default`
- **Finding VM host IDs**: `maas $PROFILE vm-hosts read`
- **Deleting a VM**: `maas $PROFILE machine delete $SYSTEM_ID`

Additional [background material on VM hosting](/t/how-to-use-virtual-machines/6500) is available for those interested in a deeper understanding.