# Manage images

MAAS deploys machines from a repository of operating system images called a SimpleStreams source. There are two image streams:

- Stable – fully tested, production-ready (default).
- Candidate – newer, less tested; use when you need support for a newer OS not yet in stable.

Each image includes Ubuntu or CentOS, a bootloader, an initramfs, and release notifications.

- Images sync hourly at the region level.
- Rack controllers cache files as needed for deployment.

## Switch image streams

You can change streams at any time.

UI

- *Images* > *Change source* > *Custom*
- Set *URL* to:
  - Stable: `http://images.maas.io/ephemeral-v3/stable`
  - Candidate: `http://images.maas.io/ephemeral-v3/candidate`

CLI

```text
BOOT_SOURCE_ID=$(maas $PROFILE boot-sources read)
```

## Manage images

Images must be downloaded before deployment. Choose which ones to keep locally.

UI

- *Main menu* > *Images* > *Select/Unselect* > *Save selection*

CLI

```text
maas $PROFILE boot-sources read  # list boot sources
maas $PROFILE boot-source-selections create $SOURCE_ID     os="ubuntu" release="$SERIES" arches="$ARCH"     subarches="$KERNEL" labels="*" # select boot sources
maas $PROFILE boot-resources read # list images
maas $PROFILE boot-resources import # select images
```

## Additional CLI management

### Delete a boot source

```text
maas $PROFILE boot-source delete $SOURCE_ID
```

### Update a boot source

```text
maas $PROFILE boot-source update $SOURCE_ID     url=$URL keyring_filename=$KEYRING_FILE
```

### Add a new boot source

```text
maas $PROFILE boot-sources create     url=$URL keyring_filename=$KEYRING_FILE
```

💡 Use `/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg` if the new source mirrors the official streams.

## Use a custom mirror

UI

- *Images* > *Change source* > *Custom* > enter *URL* > *Connect*
- For advanced settings, choose *Show advanced options*
- Use a local mirror (see below) for faster imports

## Use a local mirror

A local SimpleStreams mirror improves sync performance.

### Install SimpleStreams

```text
sudo apt install simplestreams
```

### Define helper variables

```text
KEYRING_FILE=/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg
IMAGE_SRC=https://images.maas.io/ephemeral-v3/stable
IMAGE_DIR=/var/www/html/maas/images/ephemeral-v3/stable
```

### Mirror kernels

```text
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

```text
URL=https://$MIRROR/maas/images/ephemeral-v3/stable/
KEYRING_FILE=/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg
```

Replace `$MIRROR` with your mirror server hostname.

## Safety nets

- Production use: stick to the *stable* stream.
- Candidate images may contain bugs — only use if you need newer OS support.
- Check mirrors after setup to confirm availability.

## Next steps

- Learn [About MAAS images](explanation/images.md)
- Discover [How to build custom images](how-to-guides/build-custom-images.md)
- Find out [How to deploy a real-time kernel](how-to-guides/deploy-a-real-time-kernel.md)
