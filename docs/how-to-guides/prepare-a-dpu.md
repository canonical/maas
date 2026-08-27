# Prepare a DPU

Deployment scripts are a MAAS feature for running custom logic during a machine's deployment. We can use them to prepare a BlueField DPU so MAAS can enroll it: the script flashes a BlueField software bundle (BFB) onto the DPU and leaves it PXE-bootable.
Once the DPU network boots, MAAS commissions and deploys it like any other machine (see the other MAAS DPU guides).

The preparation work runs on the DPU's host, which reaches the DPU through the `rshim` driver.

Today this is done by hand after the host is deployed; this guide describes how to use a deployment script to automate that work.

## Host-side preparation script

A deployment script runs in the host's ephemeral environment, so anything it installs or writes on the host is thrown away on reboot.
That is normally a limitation, but for DPU preparation it is exactly what we want:

- The script's *effect* is not on the host filesystem. `bfb-install` writes the BFB onto the DPU's own storage, where it stays when the host reboots.
  The DOCA host tools only need to exist during the flash, so installing them into the throwaway host OS is fine.
- It is hardware-facing and one-shot: reach the DPU over `rshim`, bring it to a known state, and hand it back to MAAS.
  Nothing needs to persist on the host to achieve that.

The flow we want to automate runs on the DPU's host and proceeds as follows:

1. Install the DOCA host tools (this provides `rshim` and `bfb-install`).
2. Enable and start the `rshim` service; confirm `/dev/rshim0` appears.
3. Download a BFB bundle matching the DPU and OS.
4. `bfb-install --rshim rshim0 --bfb <file>` to flash the DPU to a known state.
5. Set the DPU to PXE boot (console / `efibootmgr` / Redfish) so MAAS can enroll it.

With that flow as a reference, we can implement the deployment script.

```shell
#!/usr/bin/env bash

# --- Start MAAS 1.0 script metadata ---
# name: 60-dpu-prepare
# title: Prepare BlueField DPU (flash BFB) for MAAS enrollment
# description: Install DOCA host tools and flash the BFB so the DPU can PXE-enroll
# script_type: deployment
# timeout: 00:30:00
# --- End MAAS 1.0 script metadata ---

set -euo pipefail

# Match these to the HOST's Ubuntu release/arch and the BFB you want to flash.
DOCA_URL="${DOCA_URL:-https://linux.mellanox.com/public/repo/doca/2.9.0/ubuntu22.04/x86_64/}"
BFB_URL="${BFB_URL:-https://content.mellanox.com/BlueField/BFBs/Ubuntu22.04/bf-bundle-2.7.0-33_24.04_ubuntu-22.04_prod.bfb}"
RSHIM_DEV="${RSHIM_DEV:-rshim0}"
BFB_FILE="/tmp/${BFB_URL##*/}"

echo "== Installing DOCA host tools (provides rshim + bfb-install)"
curl -fsSL https://linux.mellanox.com/public/repo/doca/GPG-KEY-Mellanox.pub \
  | gpg --dearmor | sudo tee /usr/share/keyrings/mellanox-archive-keyring.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/mellanox-archive-keyring.gpg] ${DOCA_URL} ./" \
  | sudo tee /etc/apt/sources.list.d/doca.list
sudo apt-get update
sudo apt-get install -y pv doca-all

echo "== Enabling rshim and waiting for the device"
sudo systemctl enable --now rshim
for _ in $(seq 1 30); do
  [[ -e "/dev/${RSHIM_DEV}/misc" ]] && break
  sleep 2
done
if [[ ! -e "/dev/${RSHIM_DEV}/misc" ]]; then
  echo "ERROR: /dev/${RSHIM_DEV} did not appear. Is a BlueField DPU attached to this host?"
  exit 1
fi

echo "== Downloading BFB bundle"
curl -fSL -o "${BFB_FILE}" "${BFB_URL}"

echo "== Flashing BFB onto ${RSHIM_DEV} (this takes several minutes)"
sudo bfb-install --rshim "${RSHIM_DEV}" --bfb "${BFB_FILE}"

echo "== BFB flashed. DPU is now in a known state; set PXE boot to enroll it in MAAS."
```

This script needs to be uploaded as a deployment script tied to the host deployment.
Update the `DOCA_URL` and `BFB_URL` variables to match the OS and architecture of the host and the DPU.
If only one DPU is attached to the host, it is safe to use `rshim0` as `RSHIM_DEV`.

**What else belongs in a deployment script?**

Anything that affects the DPU or its firmware and can be applied as a one-shot action from the host side is a good fit:

- Firmware and BFB operations: flashing, and — if needed — a firmware update matching the DOCA version before enrollment.
- Setting the DPU boot mode or PXE order so MAAS can enroll it (when scriptable via `efibootmgr` / Redfish rather than the interactive console).
- Looping over multiple DPUs on the same host (`rshim0/1/2`) to flash them in one pass.

Do not use a deployment script for:

- Configuring the DPU's own OS (DOCA runtime, `mlnx-ofed-kernel-modules`, and the `pf0hpf` / `pf1hpf` / `tmfifo_net0` interfaces).
  That belongs on the DPU side after it boots its own image, via the DPU's cloud-init or a tailored image.

## Missing interfaces after deployment

The script above prepares the DPU from the host (rshim + BFB flash + PXE).
A separate problem lives on the DPU's own deployed OS: after MAAS deploys it, only the `OOB`, `P0` and `P1` interfaces are present.
The host representor interfaces `pf0hpf` / `pf1hpf` and `tmfifo_net0` do not appear until the DOCA runtime and `mlnx-ofed-kernel-modules` (which provide `mlxbf_tmfifo`, etc.) are installed and loaded.
The workaround is to tailor a `packer-maas` image with all of it baked in.
