Operating MAAS without internet access is possible, but requires planning. Four key elements must be in place for a seamless experience:

1. Snap updates via snap proxy
2. Local package repository
3. MAAS-specific images from a local mirror
4. Other OS images from various sources

Some of these resources can also utilise a transparent proxy, minimising impact on your existing MAAS setup.

## Snap proxy

To manage snaps in an air-gapped setup, use the Snap Store Proxy. This feature is currently in a password-protected internal Beta. The proxy serves as an intermediary, eliminating the need for devices to connect to the internet. Steps to get this up:

1. Register the Snap Store Proxy on a machine with internet access.
2. Secure your proxy with HTTP.
3. Populate the proxy with snaps needed for your MAAS environment.

For detailed guidance, see the [official documentation](https://docs.ubuntu.com/snap-store-proxy/en/airgap).

## Local package update

Utilise the `reprepro` command to manage local Debian package repositories. It's the recommended way, as `apt-mirror` is no longer maintained. `Reprepro` does not require an external database and manages package signatures efficiently.

For easier access, you might want to use a transparent proxy.

## Local image mirror

MAAS allows you to mirror images locally by following these steps:

1. Install `simplestreams`.
2. Define variables for easier CLI interaction.
3. Specify image storage locations.
4. Add a new boot source pointing to the local mirror.

Check the [local image mirror guide](https://maas.io/docs/how-to-manage-images#p-9030-use-a-local-mirror) for comprehensive details.

## Non-Ubuntu images

For non-MAAS OS like CentOS or RHEL, you have two options:

- Use custom `user_data`.
- Create and store custom images in a local mirror.

## Using `user_data`

Custom `user_data` can configure CentOS or RHEL to use specific mirrors. 

## Transparent proxies

To avoid altering MAAS or Ubuntu settings, establish a transparent proxy:
 
1. Redirect Ubuntu and MAAS package requests via HTTP.
2. Create local mirrors for `archive.ubuntu.com` and `images.maas.io`.
3. Adjust DNS settings to point to these local mirrors.

This way, your existing configurations remain untouched.

