> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/controllers-understanding-region-and-rack" target = "_blank">Let us know.</a>*

Understanding controllers within the MAAS ecosystem helps to metal infrastructure. You may find it useful to [tweak your controller settings](/t/configuring-maas-controllers/5172) based on your specific network and machine count. Even consider opting for a [high availability setup](/t/ensuring-high-availability-for-controllers/5120) for robustness.

At the core of MAAS are its controllers: region controllers and rack controllers. While the region controller is the interaction hub for operators, the rack controller focuses on delivering high-bandwidth services to the machines.

## Region controllers

A region controller provides several services:

* REST API server (TCP port 5240)
* PostgreSQL database
* DNS
* caching HTTP proxy
* Web UI

It manages either an entire data centre or a specific region and orchestrates a myriad of tasks from API request routing to keeping DNS records up to date.

## Rack controllers

Rack controllers manage fabrics, offering four key services:

- DHCP
- TFTP
- HTTP (for images)
- Power management

Racks caches essential resources like OS install images for better performance.

## Fabrics

Fabrics link otherwise isolate VLANs, so they can communicate under specific conditions.

## Controllers connect

The hierarchy of communication in MAAS flows from the UI/API to the region controller, then to the rack controller, and finally to the machines. [High availability](/t/ensuring-high-availability-for-controllers/5120) (HA) setups introduce redundancy but don't alter this fundamental flow.

## Racks to machines

All communications from machines route through rack controllers. This includes everything from DNS lookups to APT cache-and-forward proxies via Squid. A unique DNS resource is created for each subnet, which machines use to find an available rack controller.

## Region and rack

Messaging between the region and rack controllers involves multiple steps.

<details><summary>Tell me about the DHCP "next-server" statement</summary>

The `next-server` directive specifies the host from which a machine should load its initial boot file. In the context of MAAS, the rack controller serving DHCP roles as this host, acting as a broker for boot file delivery.
</details>

![MAAS Architecture](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/02a7ca58b989c67c74421b9d5e0c8b32907a2de1.jpeg)