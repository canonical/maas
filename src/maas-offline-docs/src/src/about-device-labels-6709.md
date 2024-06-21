> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/labelling-devices-in-maas" target = "_blank">Let us know.</a>*

For small clusters of machines, the idea of extensively tagging and annotating might seem overkill. But as your infrastructure scales, you'll need tools to simplify navigation and management. Enter tags, annotations, and filters.

> Automatic tagging is available starting in MAAS v3.2.

## Key attributes

1. **Tags and Annotations**: They're not just for identification; they also steer machine behaviour during commissioning and deployment. Learn more with these guides:
   
   - [Tagging guide](/t/how-to-manage-tags/5928)
   - [Annotation guide](/t/how-to-annotate-machines/5929)
   - Usage guides for [machines](/t/how-to-use-network-tags/5228).
   
2. **[Filtering](/t/how-to-locate-machines/5192)**: A UI-based tool for narrowing down your machine subsets.

## Tag anatomy

**Tags** are short descriptors that can be linked to various MAAS entities:

- Machines (physical and virtual)
- VM hosts
- Controllers (rack and region)
- Storage and network interfaces
- Devices and nodes (CLI only)

**Annotations** offer a more in-depth description of machines. They can be static (always visible) or dynamic (state-dependent). 

**Tags and scripts**: Tags can also cluster scripts for tasks like commissioning and testing. 

For example:

```nohighlight
maas $PROFILE node-script add-tag $SCRIPT_NAME tag=$TAG
maas $PROFILE machine commission commissioning_scripts=$SCRIPT_NAME,$SCRIPT_TAG
```

## Automatic tags

Automatic tags bring definitions, allowing for automated machine tagging based on your set criteria through [XPath expressions](#heading--xpath-expressions). These tags can identify unique hardware features and automatically apply to newly discovered machines that meet the criteria.

**XPath expressions**: These are mapped against `lshw`'s XML output to define automatic tags. 

**Node capabilities**: These can vary from CPU features to network speeds. Most capabilities are auto-documented by `lshw`.

**Kernel options**: Tags can also carry kernel options that activate during the boot or commissioning/deployment processes. If a machine has multiple tags, kernel options from all tags combine alphabetically.