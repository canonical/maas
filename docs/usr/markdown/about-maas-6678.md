> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/overview-of-maas" target = "_blank">Let us know.</a>*

## What is MAAS?

MAAS, or "Metal As A Service," morphs your bare-metal servers into an agile cloud-like environment. Forget fussing over individual hardware; treat them as fluid resources similar to instances in AWS, GCE, or Azure. MAAS is adept as a standalone PXE/preseed service, but it truly shines when paired with [Juju](https://juju.is/docs/olm/maas), streamlining both machine and service management. Network booting via PXE? Even virtual machines can join the MAAS ecosystem.

![MAAS Architecture](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/d19eff9ef45c554d085ee1d657e4ddd810eac6df.jpeg)

## PXE booting

PXE, or "Preboot Execution Environment" (often called "pixie"), empowers machines to load OS images via network interfaces. This requires a PXE-compatible NIC, configurable through software switches.

## Why choose MAAS?

MAAS transforms a vast collection of physical servers into flexible resource pools. It seamlessly provisions, re-purposes, and deallocates resources, letting you focus on the bigger picture. Want to delve into hardware details before deployment? MAAS scrutinises attached USB and PCI devices, allowing optional exclusion.

## System management

MAAS wraps 13 critical features into one cohesive interface:

1. Responsive web UI
2. Broad OS support: Ubuntu, CentOS, Windows, RHEL
3. IP address management (IPAM)
4. API/CLI access
5. Optional high availability
6. IPv6 readiness
7. Hardware inventory
8. DHCP and DNS for network devices
9. DHCP relay
10. VLAN and fabric support
11. Network time protocol (NTP)
12. In-depth hardware testing
13. Composable hardware

Easily scale and manage your data centre with these integrated tools.

![MAAS Features](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/00968a71b82ce01c45ae3b345ed6b1270d0927bf.jpeg)

## Scriptable CLI

If CLI is your preference, here are 11 features you shouldn't overlook:

1. Broad OS support: Ubuntu, CentOS, Windows, RHEL
2. IPAM
3. Optional high availability
4. IPv6 readiness
5. Hardware inventory
6. DHCP and DNS for network devices
7. DHCP relay
8. VLAN and fabric support
9. NTP
10. Hardware testing
11. Composable hardware

![CLI Experience](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/40fdae53957095e5a830458dc5c7a62ea5d78c10.jpeg)

MAAS plays well with configuration management tools, receiving endorsements from both [Chef](https://www.chef.io/chef) and [Juju](https://jaas.ai/) teams.

>**Note**: Windows and RHEL compatibility may require [Ubuntu Pro](https://www.ubuntu.com/support) for seamless integration.

## Resource efficiency

MAAS architecture comprises two linchpins: the region controller and the rack controller. The former orchestrates data centre-wide operations while the latter focuses on individual racks. For a streamlined setup, co-locating these controllers is advisable, and it's the default in MAAS installations. This config also brings DHCP into the mix.

![MAAS Controllers](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/3ad2b128fbc034e9f575f21c0415a6e6c55baea3.jpeg)

For a deep dive into these components, refer to [Concepts and terms](/t/reference-maas-glossary/5416) may warrant additional controllers.