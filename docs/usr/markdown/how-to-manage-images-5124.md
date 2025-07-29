MAAS relies on a repository of OS images for machine deployment, called a SimpleStreams source.  There are two streams: candidate and stable.  The stable stream is fully tested, reliable, and generally considered production-ready.  Candidate images are essentially pre-release images -- they are newer, so they may have bugs or incomplete testing. Use the stable stream if you're deploying machines in production, and candidate if you need support for a newer OS version that is not yet stable. MAAS defaults to stable if you do not make a choice.

Both contain either Ubuntu or CentOS, a bootloader, an initial RAMdisk filesystem, and release notifications.  MAAS syncs images hourly at the region level. Rack controllers cache files as needed.

## Switch image streams

You can switch streams at any time using these procedures:

**UI**
*Images* > *Change source* > *Custom* > set *URL* to:
- Stable: `http://images.maas.io/ephemeral-v3/stable`
- Candidate: `http://images.maas.io/ephemeral-v3/candidate`

**CLI**
```nohighlight
BOOT_SOURCE_ID=$(maas $PROFILE boot-sources read)
```

## Manage images

Choose which images to keep locally.  Images must be downloaded before they can be deployed.

**UI**
*Main menu* > *Images* > *Select/Unselect* > *Save selection*

**CLI**
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

Use `/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg` as the keyring file if the new source is a mirror of the official streams.

## Use a custom mirror

**UI**
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
