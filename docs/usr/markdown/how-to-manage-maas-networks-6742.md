> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/networking-management" target = "_blank">Let us know.</a>*

Broadly speaking there are three essential skills you need to manage MAAS networking:

- **[Connecting MAAS nodes to controllers](/t/how-to-connect-maas-networks/5164)** is your starting point, and without it, you won't make progress. A primer on MAAS networking basics may be beneficial before diving in.

- **[Enabling DHCP](/t/how-to-enable-dhcp/5132)** is essential for MAAS to discover your machines. If DHCP is misconfigured, your machines won't obtain IP addresses or Network Boot Programs (NBPs). 

>Pro tip: DHCP-related issues often trip up MAAS setups. If you're unclear on the details, consider reading our [guide to DHCP](/t/about-dhcp-in-maas/6682).

- **[Using availability zones](/t/how-to-use-availability-zones/5152)**, which allow for machine allocation across different logical network segments, adds a layer of fault-tolerance. This is particularly useful for mission-critical applications.

If you're new to MAAS or networking in general, don't worry. We offer resources on [TCP/IP](/t/about-cloud-networking/6684) to get you up to speed.