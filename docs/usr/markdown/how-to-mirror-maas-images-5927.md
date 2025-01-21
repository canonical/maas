> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/mirroring-images-locally" target = "_blank">Let us know.</a>*

This page explains how to create and use a local mirror of MAAS images:

## Install SimpleStreams

Start by installing SimpleStreams:

```nohighlight
sudo apt install simplestreams
```

## Define helper variables

Define these variables for cleaner CLI commands:

```nohighlight
KEYRING_FILE=/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg
IMAGE_SRC=https://images.maas.io/ephemeral-v3/stable
IMAGE_DIR=/var/www/html/maas/images/ephemeral-v3/stable
```

## Mirror your kernels

Mirror your kernels with these commands:

```nohighlight
sudo sstream-mirror --keyring=$KEYRING_FILE $IMAGE_SRC $IMAGE_DIR 'arch=amd64' 'release~(bionic|focal)' --max=1 --progress
sudo sstream-mirror --keyring=$KEYRING_FILE $IMAGE_SRC $IMAGE_DIR 'os~(grub*|pxelinux)' --max=1 --progress
```

Use `--dry-run` to preview your selection. Remove it to begin the download.

MAAS saves images to the directory defined by 'IMAGE_DIR'. The new boot source URL will be `http://<myserver>/maas/images/ephemeral-v3/stable/`.

You should verify image availability at the URL above. Regularly update your mirror with `cron` to fetch the latest images.