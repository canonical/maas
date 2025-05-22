MAAS supports two SimpleStreams: candidate and stable. Both contain Ubuntu, CentOS, bootloaders, and release notifications. MAAS defaults to stable.  MAAS standard provisioning images include:

- Ubuntu and CentOS OS images.
- Bootloaders extracted from the Ubuntu archive.
- Release notifications.

MAAS syncs images hourly at the region level. Rack controller syncs run every 5 minutes. MAAS can only work with one boot source at a time.

## Switch image streams

UI**
*Images* > *Change source* > *Custom* > set *URL* to:
- Candidate: `http://images.maas.io/ephemeral-v3/candidate`
- Stable: `maas.io`

CLI**
```nohighlight
BOOT_SOURCE_ID=$(maas $PROFILE boot-sources read)
```

## Manage images

UI**
*Main menu* > *Images* > *Select/Unselect* > *Save selection*

CLI**
```nohighlight
maas $PROFILE boot-sources read  # list boot sources
maas $PROFILE boot-source-selections create $SOURCE_ID \
    os="ubuntu" release="$SERIES" arches="$ARCH" \
    subarches="$KERNEL" labels="*" # select boot sources
maas $PROFILE boot-resources read # list images
maas $PROFILE boot-resources import # select images
```

## Additional CLI management commands

### Delete a boot source

```nohighlight
maas $PROFILE boot-source delete $SOURCE_ID
```

### Update a boot source

```nohighlight
maas $PROFILE boot-source update $SOURCE_ID \
    url=$URL keyring_filename=$KEYRING_FILE
```

### Add a new boot source

```nohighlight
maas $PROFILE boot-sources create \
    url=$URL keyring_filename=$KEYRING_FILE
```

Use `/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg` as the keyring file.

## Use a custom mirror

UI**
- *Images* > *Change source* > *Custom* > enter *URL* > *Connect*.
- For advanced options, select *Show advanced options*.
- Set up a local mirror (below) for faster imports.

## Use a local mirror

A local mirror can improve image sync performance.

### Install SimpleStreams

Start by installing SimpleStreams:
```nohighlight
sudo apt install simplestreams
```

### Define helper variables

Define these variables for cleaner CLI commands:
```nohighlight
KEYRING_FILE=/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg
IMAGE_SRC=https://images.maas.io/ephemeral-v3/stable
IMAGE_DIR=/var/www/html/maas/images/ephemeral-v3/stable
```

### Mirror your kernels

Mirror your kernels with these commands:
```nohighlight
sudo sstream-mirror --keyring=$KEYRING_FILE $IMAGE_SRC $IMAGE_DIR 'arch=amd64' 'release~(bionic|focal)' --max=1 --progress
sudo sstream-mirror --keyring=$KEYRING_FILE $IMAGE_SRC $IMAGE_DIR 'os~(grub*|pxelinux)' --max=1 --progress
```

Use `--dry-run` to preview your selection.

MAAS saves images to the directory defined by 'IMAGE_DIR'. The new boot source URL will be `http://<myserver>/maas/images/ephemeral-v3/stable/`.

Verify image availability at the URL above. Regularly update your mirror with `cron` to fetch the latest images.

Set `URL=https://$MIRROR/maas/images/ephemeral-v3/stable/` and `KEYRING_FILE=/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg`, where `$MIRROR` is the mirror server.

