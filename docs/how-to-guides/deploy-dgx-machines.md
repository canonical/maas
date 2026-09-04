# Deploy DGX machines

Use MAAS cloud-init user-data to install the platform config packages, NVIDIA kernel,
and GPU drivers recommended for NVIDIA DGX machines. This configuration reboots
the machine after installation, so MAAS might report the machine as deployed
a few minutes before it is ready to use.

## What you'll need

* A commissioned DGX (Vera, Grace, B200, H100, A100, or similar) machine that is ready to deploy in MAAS.
* An Ubuntu 26.04 image imported into MAAS.
* Internet access from the deployed machine to Ubuntu archives and PPAs.

## Deploy the machine

1. In the MAAS UI, select the DGX machine and choose **Deploy**.
2. In the deployment panel, select Ubuntu 26.04.
3. Expand **Cloud-init user-data** and enter the following configuration:

```yaml
#cloud-config
package_update: true

packages:
  - ubuntu-drivers-common
  - software-properties-common

write_files:
  - path: /usr/local/sbin/dgx-cloud-init-data
    permissions: "0755"
    content: |
      #!/usr/bin/env bash
      set -euo pipefail

      export DEBIAN_FRONTEND=noninteractive

      # Detect applicable OEM metapackages.
      oem_output="$(ubuntu-drivers list-oem)"
      oem_packages=()

      while IFS= read -r package; do
          [[ -z "${package}" ]] && continue

          if [[ ! "${package}" =~ ^[a-zA-Z0-9][a-zA-Z0-9+.-]*$ ]]; then
              echo "Invalid package returned by ubuntu-drivers: ${package}" >&2
              exit 1
          fi

          oem_packages+=("${package}")
      done <<< "${oem_output}"

      # First installation adds any archive configured by the metapackage.
      for package in "${oem_packages[@]}"; do
          apt-get install \
              --yes \
              --install-recommends \
              "${package}"
      done

      apt-get update

      # Reinstall/upgrade metapackages from their OEM archives.
      for package in "${oem_packages[@]}"; do
          apt-get install \
              --yes \
              --install-recommends \
              "${package}"
      done

      ubuntu-drivers install --gpgpu

      if [[ "$(dpkg --print-architecture)" == "arm64" ]]; then
          add-apt-repository \
              --yes \
              ppa:canonical-nvidia/nvidia-virtualization
      fi

runcmd:
  - ["/usr/local/sbin/dgx-cloud-init-data"]

power_state:
  mode: reboot
  delay: now
  message: Rebooting after OEM and NVIDIA driver installation
  condition: true
```

4. Select **Start deployment for machine**.
5. Wait for cloud-init to install the packages and reboot the machine.

## Verify the deployment

After the machine reboots, connect to it and confirm that cloud-init finished:

```bash
cloud-init status --wait
```

Confirm that the NVIDIA driver can communicate with the GPUs:

```bash
nvidia-smi
```

If cloud-init or the driver installation failed, inspect
`/var/log/cloud-init-output.log` on the deployed machine.
