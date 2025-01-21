> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/virtual-machines" target = "_blank">Let us know.</a>*

We favour [LXD](https://linuxcontainers.org/lxd/introduction/) as our trusted VM host, optimising all MAAS VM functionalities accordingly. In the MAAS Web UI, VM hosts are referred to as "KVMs".

For those already familiar with KVMs and LXD VMs, you can proceed to [set up LXD](/t/how-to-manage-virtual-machines/5148) as per your workload requirements. The article will delve into the theory behind MAAS VM hosts for those who need a refresher.

## MAAS VM hosting

MAAS VM hosts enable dynamic node composition using your available hardware resources like disk space, memory, and cores. Virtual machines can be created within your resource limitations, eliminating the need to worry about physical hardware constraints. 

Though LXD remains our preferred method, MAAS also provides legacy support for VM hosts created through [libvirt](https://ubuntu.com/server/docs/virtualization-libvirt).

## About VM hosts

A VM host is a machine designed to run virtual machines by distributing resources across the VMs you aim to set up. You have the flexibility to overcommit resources, meaning you can allocate more resources than actually available, provided you manage the usage wisely. Once a machine has been enlisted, commissioned, and allocated by MAAS, it's ready to function as a VM host. 

VM hosts offer unique benefits when integrated with Juju, including dynamic VM allocation with custom interface constraints. The web UI in MAAS offers a powerful platform to manage VMs, which are logically grouped by VM host. Notable features include:

- Juju integration
- Visual tools for resource management
- Overcommit ratio settings for CPU and RAM
- VM assignment to resource pools for logical groupings
- Storage pool tracking and default assignments
- Multi-network VM creation based on various parameters

In essence, a VM host is a machine that you designate to run your virtual machines. It divides its available resources amongst the VMs you wish to create, depending on the choices you make during each VM setup.

## About VM host storage pools

"Storage pools" are storage assets managed by a VM host. These are specific storage quantities reserved for VM usage and can be broken down into individual storage volumes for block device assignment to VMs.

>**Pro tip**: For LXD VM hosts, it's possible to allocate a single block device from the storage pool to each VM.

## Viewing VM host storage pools in the UI

The MAAS web UI offers a straightforward way to monitor your VM host storage pools. A quick look will provide insights into your current resource allocation.

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/3387f256f9bd02f7fc2079f119377305256973c8.jpeg)

## Viewing VM host storage pools via the CLI

To fetch VM host storage pool details through the CLI, you can use the following command:

```nohighlight
maas $PROFILE vm-host read $VM_HOST_ID
```

For a tabular representation, use:

```nohighlight
maas admin vm-host read 5 \
| jq -r '(["NAME","TYPE","PATH","TOTAL","USED","AVAIL"]) 
| (,. map(length*"-"))), (.storage_pools[] 
| [.name, .type, .path, .total, used, .available]) | @tsv' \
| column -t
```

## LXD VM host authentication

Beginning with version 3.1, MAAS improves the user experience of connecting an existing LXD server to MAAS. It streamlines manual steps and enhances security through the use of certificates. Previously, each MAAS region/rack controller required a separate certificate. Adding an LXD VM host required either adding certificates from every controller that could access the LXD server or using a trust password, which isn't recommended for production use. MAAS 3.1 addresses these issues by managing individual keys and certificates for each LXD server, making it easier to authorise MAAS in LXD.

## On-the-spot certificate creation

In these more recent versions, the focus is on using certificates for authenticating LXD servers—a best practice in production environments. The new version provides a method to generate a unique secret key and certificate pair for each LXD server and presents these credentials to the user for easy addition to the LXD trust list. This unified approach:

- Simplifies the registration process by displaying the certificate for the user to add to the LXD server.
- Ensures all racks use the same key for communication with the LXD server.
- Allows seamless integration of new rack controllers.
- Provides a URL for fetching the certificate, useful for `curl` operations.

## Bringing your own certificates

MAAS 3.1 and higher also allow you to import an existing key and certificate pair if your LXD server already trusts it. The system will store your credentials instead of creating new ones. 

>**Pro tip**: Imported keys must not have a passphrase for MAAS to use them.

## LXD VM host projects

In more recent MAAS versions, each LXD VM host comes with a 'Project' tab that offers a summary of its current state. 

![Project Tab](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/e/e0cc264a17d67f9530ff8c2ef2bb9522fed0749a.png)

Here, you can view the project details, its current resource allocation, and even perform actions on existing VM hosts or create new ones. Another tab provides a rundown of resource usage for your LXD VM host. 

![Resource Details](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/d/d67cf384d6fe903274893eb50a098518d2c1295d.png)

This view lets you map or un-map resource usage to NUMA nodes.

## About VM host settings

VM host settings can be easily modified under the 'Settings' tab. This includes options like the VM host's address, password, network zone, resource pool, and memory and CPU overcommit sliders.

![Settings](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/2/253afc122d61145be656bb5c3811f9b6c6caa708.png)

## LXD vs libvirt

Both libvirt KVMs and LXD VMs are based on QEMU, but LXD VMs offer more advantages such as enhanced security and a robust API. Unlike libvirt KVMs, LXD VMs can be managed remotely without requiring SSH access.

## VMs and NUMA

MAAS provides extensive tools for optimising the use of NUMA with virtual machines. You get a detailed view of resources allocated to each NUMA node, allowing you to manage your VMs more efficiently. Additional features like SR-IOV and hugepages support are also included.

## Support for NUMA, SR-IOV, and hugepages

VM host management has been revamped to support configurations like NUMA, SR-IOV, and hugepages. Whether you're using the UI or CLI, you can view detailed information on resource allocation per NUMA node, and even configure hugepages for your VM hosts.

## About over-committed resources

Over-committed resources are those allocated beyond what's available in the physical resource. Using sliders on the configuration page, you can limit whether MAAS will attempt to overcommit CPU and memory. The input fields to the right of the sliders accept floating-point values from 0 to 10, with a default value of 1.

The following shows four theoretical examples of these ratios and how they affect physical resource allocation:

1.  `8 physical CPU cores  * 1 multiplier     = 8 virtual CPU cores`
2.  `8 physical CPU cores  * 0.5 multiplier   = 4 virtual CPU cores`
3.  `32 physical CPU cores * 10.0 multiplier  = 320 virtual CPU cores`
4.  `128GB physical memory  * 5.5 multiplier  = 704G virtual Memory`

You can currently view overcommit ratios in the MAAS UI:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/27a8f21392af3d29a500e33f99e1f79c578cf29c.jpeg) 

Because of the graphical nature of this view, there are currently no plans to duplicate these views within the MAAS CLI.

Over-committing resources allows a user to compose many MAAS-managed machines without worrying about the physical limitations of the host. For example, on a physical host with four cores and 12 GB of memory, you could compose four libvirt machines, each using two cores and 4 GB of memory.  This arrangement over commits the available physical resources. Provided you never run all four VMs simultaneously, you would have all the benefits of MAAS-managed VMs without over-taxing your host.