
## Cheat sheet
| Resource | What to provide | How to verify |
| Snaps | Enterprise Store with required snaps | `snap info maas` works without internet |
| Packages | Local Debian repo via `reprepro` | `apt update` succeeds |
| Ubuntu images | Local `simplestreams` mirror | `maas $PROFILE boot-resources read` lists images |
| Other OS images | Custom images or `user_data` | Deploy CentOS/RHEL node |
| Proxy (optional) | Transparent proxy for MAAS + Ubuntu requests | DNS redirects to your mirror |


## Why this matters
MAAS can run in an air-gapped environment (no internet access), but only if you prepare the right local resources.  Without preparation, you’ll run into failed package installs, missing images, and broken updates.

This guide shows you how to:

- Provide snaps from an Enterprise Store
- Host a local package repository
- Mirror Ubuntu images locally
- Support other OS images (CentOS, RHEL, etc.)
- Optionally use a transparent proxy to simplify access


## Prepare the Enterprise Store (snaps)

Snaps are central to MAAS.  In an offline environment, you need a private Enterprise Store.

1. Register the Enterprise Store on a machine with internet access.
2. Secure the deployment with HTTPS.
3. Populate the store with the snaps required by your MAAS environment.

For detailed steps, see [Enterprise Store docs](https://documentation.ubuntu.com/enterprise-store).


## Host a local package repository

MAAS rack and region controllers still depend on Debian packages.  Use `reprepro` to build and manage a local mirror:

- `reprepro` is actively maintained (unlike `apt-mirror`).
- No external database required.
- Handles package signatures efficiently.

You can also front this with a transparent proxy for easier access.


## Mirror MAAS images locally

MAAS must download Ubuntu OS images for commissioning and deployment.  Without internet, mirror them yourself:

1. Install `simplestreams`.
2. Define environment variables for CLI interaction.
3. Configure local storage paths.
4. Add a new boot source in MAAS pointing to your local mirror.

See [local image mirror guide](https://canonical.com/maas/docs/how-to-manage-images).


## Provide non-Ubuntu images

For CentOS, RHEL, or other OSes:

- Use custom `user_data` to configure the installer with your own package mirrors.
- Or build and store custom images in your local mirror for MAAS to deploy.


## Use a transparent proxy (optional)

A transparent proxy makes offline operation less intrusive:

1. Redirect Ubuntu and MAAS package requests via HTTP.
2. Mirror both `archive.ubuntu.com` and `images.maas.io`.
3. Adjust DNS so that requests resolve to your local mirrors.

This way, MAAS and Ubuntu configurations don’t need to be altered — requests are intercepted and handled locally.


## Safety nets

- Test each mirror before disconnecting from the internet (`apt update`, `snap info`, `maas boot-resources import`).
- Confirm MAAS can download and deploy at least one image end-to-end.
- Document your local mirror hostnames and ensure DNS overrides are in place.


## Next steps
- Find out how to [secure MAAS](https://canonical.com/maas/docs/how-to-enhance-maas-security)
- Learn more about [MAAS security](https://canonical.com/maas/docs/about-maas-security)
- Read up on [networking in MAAS](https://canonical.com/maas/docs/about-maas-networking)
