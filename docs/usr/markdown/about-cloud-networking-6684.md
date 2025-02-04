> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/cloud-networking-essentials-for-maas" target = "_blank">Let us know.</a>*

## AAC is outmoded

Mainframes were once epicentres: Monolithic applications ran with direct I/O connections. Local Area Networks (LANs) (like Banyan Vines) broke this pattern by joining CPUs from different machines. This idea gave rise to the OSI model, setting the stage for the decentralised Web. Today, generic switches and servers make up both cloud and bare-metal clusters, shifting the focus further from application-specific servers and toward virtualisation.

![Traditional AAC Layout](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/e/e15a35da43b2788883ec014efb1832b8f641e872.jpeg)

In the Access-Aggregation-Core (AAC) setup, the focus was on hardware. Switch-to-server ratios were high, because these networks used hardware-based packet switching, rife with congestion issues and address conflicts. AAC became a bottleneck because of unforeseen server-to-server traffic, leading to:

- Shortage of Virtual LANs (VLANs)
- Spanning Tree Protocol (STP) switch-count constraints
- Packet flood complications
- Risks of VLAN partitioning
- ARP table overloads

## Disaggregation

![Cloud Design](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/f/fd86954e48538ce9ba8fc6e02df23b0a2337ef12.jpeg)

Contemporary cloud networks use a spine-and-leaf architecture of inexpensive, uniform switches and servers. All switches talk, reducing congestion and bypassing hardware limitations. Switch disaggregation is the mantra for cloud networks. Router and switch functionalities have distinct hardware and software components, paving the way for standard and budget-friendly switching, more agile networks, simpler upgrades, and a nearly-invisible network presence.

## Routing

Moving packets using IP addresses is simple. Packet forwarding, though, still hops messages to the destination. Routing algorithms need to be very efficient; currently, that efficient algorithm is multicast routing. A single packet can serve multiple servers efficiently, but only those interested in receiving it. With multicast, only the designated Network Interface Cards (NICs) process the packets, making it a perfect fit for scalable operations like software updates or database refreshes.

For example, IPv6 has fully embraced multicast, replacing ARP with neighbor discovery protocols for better efficiency and scaling.
