> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/about-device-labels" target = "_blank">Let us know.</a>*  

As your infrastructure scales, device labels simplify navigation and management.

## Key attributes

- Tags & annotations: Identify machines and influence behavior.
- Filtering: UI-based machine search.  

> *Learn about usage: [Tags](/t/how-to-manage-tags/5928) | [Annotations](/t/how-to-annotate-machines/5929) | [Search](/t/how-to-locate-machines/5192)*

## Tag anatomy

- Tags: Short descriptors for machines, VM hosts, controllers, storage, and network interfaces.  
- Annotations: Detailed, static or dynamic descriptions.  
- Scripts: Tags can group scripts for commissioning/testing.  

## Automatic tags

> *Automatic tagging is available in MAAS v3.2+.*

Define machine criteria via XPath expressions. Tags apply automatically based on:  
- Hardware features (mapped from `lshw` XML output).  
- Node capabilities (CPU, network speed, etc.).  
- Kernel options, combined alphabetically at boot.  
