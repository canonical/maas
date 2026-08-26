# Manage images

MAAS deploys machines from a repository of operating system images called a SimpleStreams source. There are two image streams:

- Stable – fully tested, production-ready (default).
- Candidate – newer, less tested; use when you need support for a newer OS not yet in stable.

Each image includes Ubuntu or CentOS, a bootloader, an initramfs, and release notifications.

- Images sync hourly at the region level.
- Rack controllers cache files as needed for deployment.

## Configure boot sources

MAAS comes with two default boot sources: stable and candidate. You can configure multiple boot sources, each with a priority value. When the same image is available in multiple sources, MAAS downloads it from the source with the highest priority.

### Default boot source URLs

- Stable: `http://images.maas.io/ephemeral-v3/stable`
- Candidate: `http://images.maas.io/ephemeral-v3/candidate`

### List boot sources

**UI**

- *Settings* > *Images* > *Sources*

**CLI**

```sh
maas $PROFILE boot-sources read
```

### Add a boot source

**UI**

- *Settings* > *Images* > *Sources* > *Add boot source*
- Enter the *URL*
- Set a unique *Priority* value
- Save your configuration

**CLI**

```sh
maas $PROFILE boot-sources create \
  url=$URL \
  keyring_filename=$KEYRING_FILE \
  priority=$PRIORITY_VALUE
```

Replace `$URL` with your SimpleStreams URL, `$KEYRING_FILE` with the keyring path, and `$PRIORITY_VALUE` with an integer (higher values take precedence). Each boot source must have a unique priority.

### Example: Stable with candidate fallback

This example configures stable as the primary source and candidate as a fallback.

**CLI**

```sh
# Add stable stream with high priority
maas admin boot-sources create \
  url=http://images.maas.io/ephemeral-v3/stable \
  keyring_filename=/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg \
  priority=100

# Add candidate stream with lower priority
maas admin boot-sources create \
  url=http://images.maas.io/ephemeral-v3/candidate \
  keyring_filename=/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg \
  priority=50
```

When both streams have the same image, MAAS downloads it from the stable stream only (priority 100).

### Update boot source priority

**CLI**

```sh
maas $PROFILE boot-source update $SOURCE_ID priority=$PRIORITY_VALUE
```

### Disable a boot source

You can disable a boot source to prevent MAAS from downloading images from it. Disabled sources are excluded from image synchronization, but their already-downloaded images remain on disk and can still be deployed. These images are deleted when you select the same image from an active boot source.

**UI**

- *Settings* > *Images* > *Sources*
- Find the boot source you want to disable
- Toggle the *Enabled* switch to off
- Save your configuration

**CLI**

```sh
# Disable a boot source
maas $PROFILE boot-source update $SOURCE_ID enabled=false

# Re-enable a boot source
maas $PROFILE boot-source update $SOURCE_ID enabled=true
```

## Download images

Images must be downloaded before deployment. Choose which ones to keep locally.

**UI**

- *Main menu* > *Images* > *Select/Unselect* > *Save selection*

**CLI**

```sh
maas $PROFILE boot-sources read  # list boot sources
maas $PROFILE boot-source-selections create $SOURCE_ID     os="ubuntu" release="$SERIES" arches="$ARCH"     subarches="$KERNEL" labels="*" # select boot sources
maas $PROFILE boot-resources read # list images
maas $PROFILE boot-resources import # select images
```

## Images synchronization settings

You can change the synchronization interval, or disable the synchronization entirely, in *Settings* > *Images* > *Synchronization*.

## Additional CLI management

### Delete a boot source

```sh
maas $PROFILE boot-source delete $SOURCE_ID
```

### Update a boot source

```sh
maas $PROFILE boot-source update $SOURCE_ID     url=$URL keyring_filename=$KEYRING_FILE
```

### Add a new boot source

```sh
maas $PROFILE boot-sources create     url=$URL keyring_filename=$KEYRING_FILE
```

💡 Use `/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg` if the new source mirrors the official streams.

## Use a custom mirror

**UI**

- *Images* > *Change source* > *Custom* > enter *URL* > *Connect*
- For advanced settings, choose *Show advanced options*
- Use a local mirror (see below) for faster imports

## Use a local mirror

A local SimpleStreams mirror improves sync performance.

### Install SimpleStreams

```sh
sudo apt install simplestreams
```

### Define helper variables

```sh
KEYRING_FILE=/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg
IMAGE_SRC=https://images.maas.io/ephemeral-v3/stable
IMAGE_DIR=/var/www/html/maas/images/ephemeral-v3/stable
```

### Mirror kernels

```sh
sudo sstream-mirror --keyring=$KEYRING_FILE $IMAGE_SRC $IMAGE_DIR 'arch=amd64' 'release~(bionic|focal)' --max=1 --progress
sudo sstream-mirror --keyring=$KEYRING_FILE $IMAGE_SRC $IMAGE_DIR 'os~(grub*|pxelinux)' --max=1 --progress
```

- Use `--dry-run` to preview.
- Images save to `$IMAGE_DIR`.
- New boot source URL: `http://<myserver>/maas/images/ephemeral-v3/stable/`.

### Verify and update

- Open the URL above to confirm access.
- Schedule regular updates with `cron`.

### Configure MAAS to use your mirror

```sh
URL=https://$MIRROR/maas/images/ephemeral-v3/stable/
KEYRING_FILE=/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg
```

Replace `$MIRROR` with your mirror server hostname.

## Safety nets

- Production use: stick to the *stable* stream.
- Candidate images may contain bugs — only use if you need newer OS support.
- Check mirrors after setup to confirm availability.

## Next steps

- Learn [About MAAS images](/explanation/images.md)
- Discover [How to build custom images](/how-to-guides/build-custom-images.md)
- Find out [How to deploy a real-time kernel](/how-to-guides/deploy-a-real-time-kernel.md)
