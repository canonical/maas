> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/about-availability-zones" target = "_blank">Let us know.</a>*

An availability zone is an organizational unit containing nodes, with each node belonging to exactly one zone. Zones help with fault tolerance, service performance, and power management. Machines can be allocated from specific zones in production.  

## Fault tolerance

Fault tolerance ensures a system continues operating despite failures. MAAS zones can improve resilience by separating resources based on power supply, network segmentation, or data center location.  

- Machines working together should be in the same zone.  
- The entire service should be replicated in another zone for redundancy.  

## Service performance  

Service performance focuses on efficiency and speed. MAAS zones help by placing nodes close to performance-critical resources.  

- Allocate nodes based on network topology and latency needs.  
- Use smaller, well-defined zones to group resources efficiently.  

## Power management

Power management optimizes power usage and cooling.  

- Distribute high-power or heat-generating nodes across zones.  
- Prevent hotspots and balance power consumption.  

## Default zone  

A newly installed MAAS includes a default zone that holds all nodes. You cannot remove or rename this zone, but you can create new ones and assign machines. If zones aren’t relevant to your setup, you can ignore them.
