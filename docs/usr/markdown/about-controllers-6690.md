Understanding how controllers work in MAAS is critical to managing metal infrastructure reliably. MAAS uses two types of controllers — region controllers and rack controllers — to distribute responsibilities and scale service delivery. These components form a layered architecture, designed to balance high-throughput demands with robust coordination.

You may find it useful to adjust your controller settings based on your network design and expected load. As your environment grows, consider a high availability (HA) setup to protect against downtime and performance degradation.

## Controller roles

### Region controllers

Region controllers serve as the interface layer for users and automation. It manages either an entire data center or a specific region and orchestrates a myriad of tasks from API request routing to keeping DNS records up to date.

These services enable users to interact with MAAS, manage infrastructure, and coordinate operations across all rack controllers.

Region controllers manage one or more racks (and by extension, the machines those racks serve). They are not stateless: they maintain session context, perform validation, and coordinate concurrent tasks. As such, load-balancing region controllers requires care, especially under high load.

### Rack controllers

Rack controllers deliver high-bandwidth services directly to machines. Each rack controller provides:

* DHCP (for address assignment)
* A recursive DNS resolve
* TFTP (for PXE boot)
* HTTP (for image distribution)
* An NTP stratum
* Power management
* Reading APR for network discovery (collected data is sent back to the region controller for persistent storage)

Rack controllers also cache critical assets such as OS images to reduce network congestion and improve provisioning speed. They serve as the final handoff layer between MAAS and bare-metal machines.

## Communication flow

The MAAS controller hierarchy works as follows:

1. Users and automation tools interact with region controllers.
2. Region controllers communicate with all rack controllers.
3. Rack controllers interact with machines.

All provisioning, configuration, and control flows pass through this hierarchy.

![MAAS Architecture](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/02a7ca58b989c67c74421b9d5e0c8b32907a2de1.jpeg)

