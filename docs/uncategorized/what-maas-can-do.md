# What MAAS can do

Metal as a Service (MAAS) is an open-source tool from Canonical that brings cloud-like agility to physical servers. In essence, MAAS lets you treat a data center of bare-metal machines as if it were a cloud, enabling on-demand provisioning, automated configuration, and life-cycle management of physical servers. It provides fast self-service provisioning for a wide range of operating systems – including Ubuntu, Windows, CentOS, RHEL, SUSE, and even VMware ESXi – allowing users to deploy or re-image machines with a few clicks or API calls. By implementing many of the standard features of public cloud on bare metal (such as user metadata and cloud-init for automation), MAAS gives end-users full control of deployed physical machines as if they were cloud instances.

MAAS is designed for technical users and IT teams who need to efficiently manage hardware at scale. Whether you are evaluating MAAS for an enterprise data center, integrating it into a private cloud solution, or managing specialized environments like HPC clusters or edge deployments, MAAS provides a comprehensive set of capabilities. The following sections detail what MAAS can do – its key features and how they apply to various use-case scenarios (enterprise IT, cloud integrators, HPC, edge, testing/CI, etc.), with examples of how MAAS adds value in each environment.

## Key capabilities of MAAS

MAAS offers a rich feature set to automate bare-metal infrastructure.

### Self-service bare-metal provisioning

MAAS enables on-demand provisioning of physical servers with zero-touch, self-service deployment. Users can rapidly deploy machines via a web UI or API, choosing from multiple OS images (Ubuntu, Windows, CentOS, RHEL, SUSE, ESXi, etc.). This gives end-users an on-premise, cloud-like experience; they can request a machine and have it up and running with a chosen OS in minutes.

### Multi-architecture support

MAAS supports a variety of hardware architectures and platforms out-of-the-box. It can provision servers based on x86_64, ARM64 (e.g. Ampere), POWER, and IBM Z (s390x) architectures, among others. This makes it suitable for heterogeneous environments including standard x86 racks, ARM-based servers, mainframes, and more. The MAAS image repository includes many Linux distributions (Ubuntu and other Debian/RedHat based OSes) as well as Windows and hypervisor OS like ESXi, all deployable in an automated fashion, or fully customizable as desired.

### Cloud-like instance management

MAAS implements the same provisioning idioms as public clouds for bare metal. For example, it provides instance metadata service and integration with cloud-init for initialization scripts. This means when a machine is deployed, user-data scripts can run to automatically configure the server (install packages, set up accounts, etc.), just as they would on AWS EC2 or Azure VMs. End-users gain full, instance-level control over their bare-metal machines (e.g. sudo access, reboots, re-provisioning), while the ops team retains centralized management and auditing.

### Hardware discovery and inventory

When new machines are added, MAAS performs automatic hardware discovery. It uses PXE/netboot to enlist and inspect each server’s components – CPU, memory, NICs, storage devices, GPU/accelerators, etc. MAAS keeps a central inventory database of all machine hardware details down to model and serial numbers. This inventory can be continuously updated (e.g. when hardware is swapped) and provides valuable visibility into your fleet. Administrators can see what hardware is available, filter machines by attributes (like 32 GB RAM or SSD present), and track asset information.

### Storage configuration and testing

MAAS provides fine-grained control over server storage configurations. Users can configure complex storage setups during deployment – for example, set up software RAID arrays, LVM volume groups, ZFS pools, or bcache devices – all through the MAAS UI, CLI, API. MAAS also automatically tags disks by type (SSD vs HDD) to assist in placement decisions. MAAS can perform aksi disk benchmarking and health testing during commissioning: it can run nondestructive or destructive write tests to gauge disk performance and flag any faults. This ensures that each machine’s storage is configured and performing as expected before going into production.

### Network management (DHCP, DNS, IPAM)

MAAS includes integrated network services to manage the networking aspect of provisioning. It runs an IPAM (IP Address Management) service with a central database of all network subnets, VLANs, and IP addresses in use. MAAS can operate as the DHCP and DNS server for your machines, automatically allocating IPs and updating DNS records for deployed nodes (supporting both IPv4 and IPv6). It detects all NICs on each machine and can test network connectivity (e.g. which switch port a NIC is connected to, VLAN tagging) when the machine is enlisted.

### Users can model complex network topologies

You can define fabrics (collections of VLANs), subnets, VLANs and bonds in MAAS, and assign machines to networks as needed. Through MAAS, you can set up a machine’s networking (e.g. this interface on VLAN 20 with bond teaming), and MAAS will apply that during deployment and even verify connectivity. This dramatically reduces the error-prone manual work of configuring network interfaces on each server. Additionally, MAAS’s distributed architecture (region/rack controllers, described later) allows monitoring for rogue DHCP servers or duplicate IPs on the local networks, increasing reliability.

### Out-of-band power control

A core capability of MAAS is the integration with server out-of-band management interfaces. MAAS supports IPMI, Redfish, AMT, Cisco UCS Manager, Dell iDRAC, HP iLO and other BMC/IPMI-like protocols to control power and boot order on each machine. This means MAAS can remotely cycle machine power, reboot them, or direct them to PXE-boot when needed – all without manual intervention. By unifying these vendor-specific management protocols behind one tool, MAAS frees administrators from having to individually manage each server’s BMC. PXE booting and network installation are orchestrated automatically. In practice, once servers are added to MAAS and racked/cabled correctly, all provisioning actions (power on, OS install, reconfigure BIOS for PXE, etc.) are handled by MAAS, via these out-of-band controls, during the normal course of provisioning management.

### Programmable API & automation integration

MAAS is built API-first – everything in the UI can also be done via a RESTful API (with CLI and Python client bindings available). This makes it easy to integrate MAAS into broader automation and “Infrastructure as Code” workflows. For instance, cloud integrators often use MAAS’s API with configuration management or orchestration tools. Canonical’s Juju service-modeling tool can consume MAAS as a provider, automatically requesting machines from MAAS to deploy complex software (like OpenStack or Kubernetes). Similarly, MAAS can work with tools like Chef, Ansible, Terraform, or custom scripts.  For example, there is a Terraform provider for MAAS to manage hardware as code.

The API allows querying hardware state, acquiring or releasing machines, tagging resources, and more, enabling DevOps teams to script bare-metal operations just like cloud VM operations. This API-driven approach also facilitates integration into CI/CD pipelines and custom portals. In short, MAAS exposes a powerful programmatic interface for integrating bare-metal provisioning into automation ecosystems.

### KVM virtualization (micro-clouds)

In addition to physical machines, MAAS can also manage virtual machines via KVM on the bare-metal hosts. MAAS offers the ability to create lean, on-demand VMsc, effectively treating a big bare-metal server as a mini-cloud hypervisor and carving it into VMs as needed. Through MAAS, you can allocate a portion of a machine’s CPU, RAM, and storage to create VMs, which then appear as manageable nodes in MAAS. Networking for these VMs is also configured by MAAS (bridged onto the host or separate subnets). This is useful for scenarios where you want to mix virtual and physical deployments or maximize utilization of a few powerful servers.

For example, a branch office or lab could use one server to host a handful of VMs for light workloads via MAAS. The KVM pod feature simplifies hypervisor setup – admins can add an existing Ubuntu server as a MAAS KVM host, then spin up/down VMs on it through MAAS’s UI/API.

These VMs can run any OS image just like a normal machine deployment. Essentially, MAAS extends its management to include VM provisioning, providing a unified way to handle both bare metal and VM instances on-premises. This micro-cloud support lets you deploy a small cloud at the edge or in a small environment without a full OpenStack. MAAS itself orchestrates the VMs.

### High availability and scalability

MAAS is built to scale from a handful of machines to many thousands. It has a two-tier architecture: a region controller (central service/API and database) and one or more rack controllers (proxy services for DHCP/TFTP, power control, etc., usually one per rack or site). This design allows MAAS to manage multiple sites or racks under one region. In fact, MAAS can coordinate across multiple data centers or “regions” of infrastructure, managing thousands of servers while maintaining snappy performance.

For reliability, MAAS supports high-availability deployment: you can run redundant region controllers (with a PostgreSQL HA cluster on the back-end) and multiple rack controllers for failover. If one controller goes down, the other continues serving API requests or PXE boots, ensuring continuous operation. These carrier-grade HA capabilities mean MAAS can be trusted in mission-critical environments where downtime is unacceptable.

Lifecycle management and repurposing

Beyond initial provisioning, MAAS assists in the full lifecycle of servers. Machines can be commissioned (inspected and tested), deployed to an OS, then later released back into the pool, ready for redeployment for a new purpose. This makes it easy to repurpose hardware on the fly. For example, you could deploy a machine as an Ubuntu Kubernetes node one week, then release it and redeploy it as a Windows database server the next -- all remotely, within minutes. MAAS supports automated OS reinstallations and also provides workflows for decommissioning (e.g., wiping disks for security).

This flexiblity enables automated repurposing of hardware, allowing different workloads at different times on the same physical resources. By cycling machines between roles or powering them off when not in use, organizations can optimize utilization and reduce cost. MAAS even encourages power management strategies like decommissioning nodes during non-peak periods to save energy and operational costs.

### Testing and validation

Before and after deployment, MAAS can run various tests on machines to ensure they are healthy and performing correctly. During the commissioning stage, MAAS can execute hardware tests (CPU stress, memory test, storage write test, etc.) and even custom scripts defined by the user. This is particularly useful for hardware validation at scale, e.g., burn-in testing new servers or benchmarking components. MAAS’s API exposes these testing capabilities, so they can be integrated into continuous integration (CI) workflows or factory checks. MAAS essentially provides an automated way to verify that every provisioned machine meets requirements, reducing the chance of flaky hardware in production.

---

With these capabilities, MAAS serves as a Software-Defined Data Center (SDDC) provisioner that covers everything from power-on to OS install to networking and storage setup. It ties together all the low-level pieces – PXE, DHCP, DNS, IPMI/BMC control, imaging – into one cohesive system with a clean UI and API. In the following sections, we explore how these features come to life in different environments and use-case scenarios, demonstrating what MAAS can do for various categories of technical users.
