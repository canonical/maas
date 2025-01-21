> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/create-custom-images" target = "_blank">Let us know.</a>*

Custom Ubuntu images can be created with Packer. This page explains the essentials.

## Prerequisites

First, ensure your system can use packer:

1. **Install packer:**

```nohighlight
    sudo apt install packer
```
  
2. **Gather the dependencies:**

```nohighlight
    sudo apt install qemu-utils qemu-system ovmf cloud-image-utils
```

## Clone your templates

Get the essential Packer templates for MAAS:

```nohighlight
git clone https://github.com/canonical/packer-maas.git
```

## Craft your image

Create the desired image:

1. **Navigate to the template directory:**

```nohighlight
    cd packer-maas/ubuntu
```
  
2. **Start the build:**

```nohighlight
    make custom-ubuntu-lvm.dd.gz
```
  
This process will take a few moments. 

## Push to MAAS

With your image built, make it accessible to MAAS:

```nohighlight
maas $MAAS_USER boot-resources create name=custom/ubuntu architecture=amd64/generic filetype=ddgz content@=custom-ubuntu-lvm.dd.gz
```

## Deploy your image

Finally, deploy your custom image onto a node in MAAS:

1. **Deploy the image to a node:**

```nohighlight
   maas $MAAS_USER machine deploy $SYSTEM_ID osystem=$OS [$distro_series=$DISTRO]
```
  
2. **Confirm it's really yours:**

```nohighlight
    maas $MAAS_USER machines read | jq '.[] | {hostname, osystem}' 
```

For further information, consult the [Packer MAAS documentation](https://github.com/canonical/packer-maas)**^** for advanced practices.