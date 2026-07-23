# Manage switches

:::{warning}
Switch management is an **experimental, preview feature** in MAAS 3.8. It is not yet fully supported for production environments. The API, behaviour, and user interface may change in future releases without backward compatibility guarantees. This feature is not covered by standard production support. Use it in test and evaluation environments only.
:::

MAAS can automatically provision network operating systems (NOS) onto network switches using the ONIE (Open Network Install Environment) protocol. This enables zero-touch deployment of switches alongside your compute infrastructure.

This page is your reference for managing switches in MAAS.

## Prerequisites

Before you can provision switches with MAAS:

- Upload NOS installer images to MAAS (see [Upload NOS images](#upload-nos-images) below)
- Ensure your switches support ONIE (most modern data center switches do)
- Have network connectivity between MAAS and the switch management ports

## List switches

View all switches registered in MAAS.

### API

```bash
curl -X GET "http://<maas-server>:5248/MAAS/a/v3/switches" \
  -H "Authorization: Bearer <api-token>"
```

Example response:

```json
{
  "kind": "SwitchesList",
  "items": [
    {
      "id": 1,
      "target_image_id": 42,
      "target_image": "mellanox-3.8.0",
      "hal_links": {
        "self": {
          "href": "/MAAS/a/v3/switches/1"
        }
      }
    }
  ],
  "total": 1
}
```

## Get a specific switch

Retrieve details about a single switch.

### API

```bash
curl -X GET "http://<maas-server>:5248/MAAS/a/v3/switches/{switch_id}" \
  -H "Authorization: Bearer <api-token>"
```

## Register a new switch

Register a switch in MAAS by providing its management interface MAC address and optionally assigning a NOS image to it.

### API

**Register a switch without an image:**

```bash
curl -X POST "http://<maas-server>:5248/MAAS/a/v3/switches" \
  -H "Authorization: Bearer <api-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "mac_address": "00:11:22:33:44:55"
  }'
```

**Register a switch with an image:**

```bash
curl -X POST "http://<maas-server>:5248/MAAS/a/v3/switches" \
  -H "Authorization: Bearer <api-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "mac_address": "00:11:22:33:44:55",
    "image": "mellanox-3.8.0"
  }'
```

The `image` field accepts two formats:

- Full format: `onie/vendor-version` (e.g., `onie/mellanox-3.8.0`)
- Short format: `vendor-version` (e.g., `mellanox-3.8.0`) — automatically prefixed with `onie/`

## Assign or change a NOS image

Update the target operating system image for a switch.

### API

```bash
curl -X PATCH "http://<maas-server>:5248/MAAS/a/v3/switches/{switch_id}" \
  -H "Authorization: Bearer <api-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "image": "arista-4.25.0"
  }'
```

To remove the image assignment:

```bash
curl -X PATCH "http://<maas-server>:5248/MAAS/a/v3/switches/{switch_id}" \
  -H "Authorization: Bearer <api-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "image": null
  }'
```

## Delete a switch

Remove a switch from MAAS inventory.

### API

```bash
curl -X DELETE "http://<maas-server>:5248/MAAS/a/v3/switches/{switch_id}" \
  -H "Authorization: Bearer <api-token>"
```

## Upload NOS images

NOS installer images must be uploaded to MAAS as custom images. These are typically self-extracting binary installers provided by switch vendors.

### Prepare the NOS installer

1. Obtain the NOS installer binary from your switch vendor (e.g., Mellanox, Arista, Dell, Cumulus)
2. The installer should be a self-contained executable (usually a `.bin` shell script)
3. Calculate the SHA256 hash of the file: `sha256sum /path/to/installer.bin`

### Upload the image

```bash
curl -X POST "http://<maas-server>:5248/MAAS/a/v3/custom_images" \
  -H "Authorization: Bearer <api-token>" \
  -H "Content-Type: application/octet-stream" \
  -H "name: onie/mellanox-3.8.0" \
  -H "architecture: amd64/generic" \
  -H "file-type: self-extracting" \
  -H "sha256: <sha256-hash-of-file>" \
  -H "title: Mellanox Onyx 3.8.0" \
  --data-binary "@/path/to/installer.bin"
```

**Important parameters:**

- `name` header: Must start with `onie/` followed by a descriptive name (e.g., `onie/mellanox-3.8.0`)
- `architecture` header: Typically `amd64/generic` for x86 switches
- `file-type` header: Use `self-extracting` for NOS installers
- `sha256` header: The SHA256 hash of the file (required for integrity verification)
- `title` header: Human-readable description (optional)
- `--data-binary`: Path to the NOS installer binary file

### Verify the upload

```bash
curl -X GET "http://<maas-server>:5248/MAAS/a/v3/custom_images" \
  -H "Authorization: Bearer <api-token>" | jq '.items[] | select(.name | startswith("onie/"))'
```

### Example: Upload multiple NOS versions

```bash
# Mellanox Onyx 3.8.0
SHA256=$(sha256sum /opt/nos-images/onie-installer-x86_64-mlnx_x86-r3.8.0000.bin | awk '{print $1}')
curl -X POST "http://<maas-server>:5248/MAAS/a/v3/custom_images" \
  -H "Authorization: Bearer <api-token>" \
  -H "Content-Type: application/octet-stream" \
  -H "name: onie/mellanox-3.8.0" \
  -H "architecture: amd64/generic" \
  -H "file-type: self-extracting" \
  -H "sha256: $SHA256" \
  -H "title: Mellanox Onyx 3.8.0" \
  --data-binary "@/opt/nos-images/onie-installer-x86_64-mlnx_x86-r3.8.0000.bin"

# Cumulus Linux 4.4.0
SHA256=$(sha256sum /opt/nos-images/cumulus-linux-4.4.0-mlx-amd64.bin | awk '{print $1}')
curl -X POST "http://<maas-server>:5248/MAAS/a/v3/custom_images" \
  -H "Authorization: Bearer <api-token>" \
  -H "Content-Type: application/octet-stream" \
  -H "name: onie/cumulus-4.4.0" \
  -H "architecture: amd64/generic" \
  -H "file-type: self-extracting" \
  -H "sha256: $SHA256" \
  -H "title: Cumulus Linux 4.4.0" \
  --data-binary "@/opt/nos-images/cumulus-linux-4.4.0-mlx-amd64.bin"
```

## How switch provisioning works

MAAS automatically handles the DHCP configuration needed for ONIE. When a switch with ONIE support boots:

1. **DHCP discovery**: The switch's management interface sends a DHCP request with the ONIE user class.
2. **DHCP response**: MAAS DHCP server automatically recognizes the ONIE request and responds with an installer URL in the VIVSO options.
3. **Installer request**: The switch contacts the MAAS v3 API endpoint `/nos-installer` with ONIE headers (MAC address, serial number, vendor ID, etc.).
4. **Image lookup**: MAAS checks if the switch is registered and has a target image assigned.
5. **Image delivery**: If an image is assigned, MAAS streams the NOS installer binary to the switch.
6. **Installation**: The switch downloads and installs the NOS, completing the provisioning.

💡 Switches can be registered in MAAS before or after they first boot. If a switch makes a DHCP request before registration, MAAS will create an UNKNOWN interface that can later be claimed when you register the switch.

## Typical workflow

### Initial switch deployment

1. Upload the required NOS image:

   ```bash
   SHA256=$(sha256sum /path/to/installer.bin | awk '{print $1}')
   curl -X POST "http://<maas-server>:5248/MAAS/a/v3/custom_images" \
     -H "Authorization: Bearer <api-token>" \
     -H "Content-Type: application/octet-stream" \
     -H "name: onie/mellanox-3.8.0" \
     -H "architecture: amd64/generic" \
     -H "file-type: self-extracting" \
     -H "sha256: $SHA256" \
     -H "title: Mellanox Onyx 3.8.0" \
     --data-binary "@/path/to/installer.bin"
   ```

2. Register the switch with its target image:

   ```bash
   curl -X POST "http://<maas-server>:5248/MAAS/a/v3/switches" \
     -H "Authorization: Bearer <api-token>" \
     -H "Content-Type: application/json" \
     -d '{
       "mac_address": "00:11:22:33:44:55",
       "image": "mellanox-3.8.0"
     }'
   ```

3. Connect and power on the switch.

4. The switch boots into ONIE, contacts MAAS via DHCP, and automatically downloads and installs the assigned NOS.

## Custom wrapped images

Use this approach when you need to control how a switch installs its NOS.

Instead of uploading only a vendor NOS installer, upload a wrapped image (a script or self-extracting binary) that MAAS serves to ONIE. Your wrapped image can:

- download the NOS installer from MAAS or another trusted location,
- verify checksums or signatures,
- run pre-install or post-install steps,
- and execute the installer.

Use this pattern when you need custom installation logic, additional validation, or environment-specific automation.

### Creating a custom installer

Creating a custom installer can involve wrapping a NOS installer that already exists in MAAS. In this case, you must know the file's path so the custom installer can download it.
Alternatively, you can create a single binary that contains both the NOS installer and the customization logic.

#### Finding image name and path on MAAS

When assigning images to switches, MAAS uses a logical image name (`onie/<name>`). Uploaded files are stored on disk with internal filenames.

1. Check which image is currently assigned to a switch:

   ```bash
   curl -s -X GET "http://<maas-server>:5248/MAAS/a/v3/switches/{switch_id}" \
     -H "Authorization: Bearer <api-token>" | jq
   ```

2. List available ONIE custom images:

   ```bash
   curl -s -X GET "http://<maas-server>:5248/MAAS/a/v3/custom_images" \
     -H "Authorization: Bearer <api-token>" \
     | jq -r '.items[] | select(.os == "onie") | "onie/\(.release) (id=\(.id))"'
   ```

3. Check where uploaded image files are stored `/var/snap/maas/common/maas/image-storage/`

4. Match a known SHA256 to an on-disk file:

- The name on disk will usually consist of the first seven characters of the sha256sum of the uploaded image.
- Should two image files have the same first seven characters MAAS will lengthen the on-disk names until they are unique.

5. Build a rack URL for a specific file:

   ```bash
   FILENAME_ON_DISK="<value-found-above>"
   echo "http://<rack-controller>:5248/images/${FILENAME_ON_DISK}"
   ```

#### Example 1: minimal wrapped script (download and execute NOS)

The script below is a baseline you can adapt. It runs under ONIE (`#!/bin/sh`), downloads a NOS installer, optionally verifies the checksum, and executes it.

```sh
#!/bin/sh
set -eu

# Set this URL before uploading the script.
NOS_URL="http://<YOUR_WEBSERVER_IP>/path/to/nos-installer.bin"

# Set to the expected SHA256 for production. Leave empty only for testing.
NOS_SHA256=""

WORKDIR="$(mktemp -d /tmp/onie-wrap.XXXXXX)"
NOS_BIN="${WORKDIR}/nos-installer.bin"

cleanup() {
  rm -rf "${WORKDIR}"
}
trap cleanup EXIT INT TERM

echo "[onie-wrap] Downloading NOS installer from: ${NOS_URL}"

# BusyBox ONIE environments commonly provide wget but not curl.
attempt=1
max_attempts=5
while [ "${attempt}" -le "${max_attempts}" ]; do
  if wget -O "${NOS_BIN}" "${NOS_URL}"; then
    break
  fi
  if [ "${attempt}" -eq "${max_attempts}" ]; then
    echo "[onie-wrap] Failed to download NOS installer after ${max_attempts} attempts"
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep 2
done

if [ -n "${NOS_SHA256}" ]; then
  echo "[onie-wrap] Verifying SHA256"
  printf '%s  %s\n' "${NOS_SHA256}" "${NOS_BIN}" | sha256sum -c -
fi

chmod +x "${NOS_BIN}"
echo "[onie-wrap] Executing NOS installer"
"${NOS_BIN}"
```

Upload the wrapped script as a custom image:

```bash
SHA256=$(sha256sum ./onie-wrapper.sh | awk '{print $1}')
curl -X POST "http://<maas-server>:5248/MAAS/a/v3/custom_images" \
  -H "Authorization: Bearer <api-token>" \
  -H "Content-Type: application/octet-stream" \
  -H "name: onie/mellanox-wrapper-3.8.0" \
  -H "architecture: amd64/generic" \
  -H "file-type: self-extracting" \
  -H "sha256: ${SHA256}" \
  -H "title: Mellanox wrapped installer 3.8.0" \
  --data-binary "@./onie-wrapper.sh"
```

Assign this image to the switch using `image: "mellanox-wrapper-3.8.0"` (or full `onie/mellanox-wrapper-3.8.0`).

#### Example 2: package wrapper script and NOS installer in one binary

If you want to avoid runtime downloads, build one self-extracting binary that contains both wrapper logic and the NOS installer.

One practical option is `makeself`.

:::{warning}
Wrapped images can fail on some switches due to ONIE memory limits. During unpacking, large self-extracting archives may consume enough memory to trigger out-of-memory kills before the installer runs.

If you see OOM failures, prefer [Example 1: minimal wrapped script (download and execute NOS)](#example-1-minimal-wrapped-script-download-and-execute-nos).
:::

1. Install the packaging tool on your build workstation:

   ```bash
   sudo apt-get update && sudo apt-get install -y makeself
   ```

2. Prepare the payload directory:

   ```bash
   mkdir -p ./onie-bundle
   cp ./vendor-nos-installer.bin ./onie-bundle/nos-installer.bin
   cat > ./onie-bundle/run.sh <<'EOF'
   #!/bin/sh
   set -eu

   SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
   NOS_BIN="${SCRIPT_DIR}/nos-installer.bin"

   chmod +x "${NOS_BIN}"
   "${NOS_BIN}"
   EOF
   chmod +x ./onie-bundle/run.sh
   ```

3. Build the self-extracting binary:

```bash
makeself --nox11 --nocomp ./onie-bundle ./onie-wrapped-mellanox-3.8.0.bin \
  "ONIE wrapped NOS installer" ./run.sh
```

4. Upload the generated `.bin` as a MAAS custom image (`file-type: self-extracting`) and assign it to the switch.

Keep in mind:

- The image is larger, so upload and sync time increase.
- Rebuild and re-upload is needed for every NOS update.

### Adding credentials, settings, or scripts after installation

Some NOS images, such as SONiC, can be configured after the installer has finished.
In that case, keep the wrapped-image pattern and add your custom steps after the NOS installer returns successfully.

The minimal wrapped script example above already uses:

```sh
"${NOS_BIN}"
```

You can then continue with post-install steps in the same script.

Note that the exact file paths are dependent on the NOS and potentially even the version of the NOS.
We demonstrate two examples here with SONiC Community:

#### Method 1: write credentials or settings into the installed filesystem

Use this method when you want to place files directly into the installed NOS,
for example SSH keys or day-0 configuration files.

Minimal example:

```sh
# Run after the NOS installer has completed successfully.
mkdir -p /mnt/nos
mount /dev/sda3 /mnt/nos

SONIC_IMAGE_DIR=$(find /mnt/nos -maxdepth 1 -type d -name 'image-*' | head -n 1)
TARGET_PATH="${SONIC_IMAGE_DIR}/rw/home/admin/.ssh"

mkdir -p "${TARGET_PATH}"
echo "ssh-ed25519 AAAA... user@example" > "${TARGET_PATH}/authorized_keys"

umount /mnt/nos
```

Use this pattern when you need to:

- add SSH public keys,
- copy a configuration file,
- or update a file that must exist before the first boot.

#### Method 2: install first-boot scripts

Use this method when you want the switch to run one or more scripts on first
boot after the NOS has been installed.

Minimal example:

```sh
# Run after the NOS installer has completed successfully.
mkdir -p /mnt/nos
mount /dev/sda3 /mnt/nos

SONIC_IMAGE_DIR=$(find /mnt/nos -maxdepth 1 -type d -name 'image-*' | head -n 1)
HOOK_DIR="${SONIC_IMAGE_DIR}/rw/etc/config-setup/factory-default-hooks.d"

mkdir -p "${HOOK_DIR}"
cat > "${HOOK_DIR}/01-create-admin-key" <<'EOF'
#!/bin/sh
mkdir -p /home/admin/.ssh
echo "ssh-ed25519 AAAA... user@example" > /home/admin/.ssh/authorized_keys
EOF

chmod +x "${HOOK_DIR}/01-create-admin-key"
umount /mnt/nos
```

Use this pattern when you need to:

- run commands on first boot,
- apply settings that depend on the running system,
- or stage multiple initialization steps in a defined order.

If you use multiple hook scripts, name them with numeric prefixes such as
`01-setup`, `02-users`, and `03-services` so they run in a predictable order.

### Log a custom installer to syslog

MAAS does not store ONIE installer output for switches. To keep those logs, send them from a custom installer wrapper to the MAAS syslog service, or point ONIE at your own syslog server.

#### Send logs to the MAAS syslog server

The MAAS syslog listen port is `maas_syslog_port` (default `5247`). MAAS listens on both UDP and TCP on that port.

1. **Find the syslog port:**

   ```bash
   maas $PROFILE maas get-config name=maas_syslog_port
   ```

2. **Find the rack IP** on the switch management network. Use the host from the installer URL MAAS puts in the ONIE DHCP reply:

   ```text
   http://<rack-ip>:5248/MAAS/a/v3/nos-installer
   ```

   That `<rack-ip>` is the rack controller address MAAS embeds in `onie.installer_url`. You can also list rack controllers:

   ```bash
   maas $PROFILE rack-controllers read
   ```

3. **Update your custom installer wrapper** so BusyBox `syslogd` forwards to that IP and port, then write messages with BusyBox `logger`:

   ```sh
   #!/bin/sh
   set -eu

   RACK_IP="<rack-ip>"
   SYSLOG_PORT="5247"

   killall syslogd >/dev/null 2>&1 || true
   syslogd -b 3 -D -L -R "${RACK_IP}:${SYSLOG_PORT}"

   logger -t nos-installer -p local0.info "wrapper start"
   # Run your NOS installer here
   logger -t nos-installer -p local0.info "wrapper finished"
   ```

   The `-b 3 -D -L` flags match ONIE defaults. `-R` adds the remote MAAS target.

4. **Check the logs on a region controller** (or a combined region+rack host).

   Check the `journalctl` units; see [Use logging](use-logging.md). Example:

   ```bash
   journalctl -u snap.maas.pebble -t maas-machine -f MAAS_MACHINE_IP=<switch-management-ip>
   ```

   If that filter shows nothing, search by logger tag instead:

   ```bash
   journalctl -u snap.maas.pebble -t maas-machine -f | grep --line-buffered nos-installer
   ```

##### Important notes

- Always include the port in `-R <host>:<port>`. If you omit it, BusyBox defaults to UDP port `514`, which is not `maas_syslog_port`.
- BusyBox `logger` only supports `-s`, `-t`, and `-p`. It writes to the local `syslogd` and cannot open a remote host by itself.
- On a rack-only controller, MAAS receives remote messages and forwards them to the region; it does not write them to the local journal. After forwarding, `MAAS_MACHINE_IP` is the rack, so prefer the tag filter.

#### Send logs to your own syslog server

Use this when you want ONIE progress on a syslog server you operate. DHCP option 7 (`log-servers`) carries IP addresses only. ONIE starts BusyBox `syslogd` with `-R <ip>` for each address, so the remote port is always BusyBox's default: `514`.

This path cannot target the MAAS syslog service on `maas_syslog_port` (default `5247`).

1. **Run a syslog collector** that listens on UDP port `514` at an IP the switch can reach on its management network.

2. **Advertise that IP in DHCP.** MAAS does not set `option log-servers` by default. Add it on the switch management subnet with a DHCP snippet, or set the same option on an external DHCP server:

   ```bash
   maas $PROFILE subnets read
   maas $PROFILE dhcpsnippets create \
     name=onie-log-servers \
     subnet=<subnet-id> \
     enabled=1 \
     value='option log-servers <syslog-server-ip>;'
   ```

   That `value` is the dhcpd option line; use the same option on an external DHCP server.

3. **Reboot the switch into ONIE** (or renew DHCP in ONIE) so it picks up option 7.

4. **Confirm messages on your collector.** They will not appear in the MAAS journal.

**Note:** DHCP snippets are deprecated as of MAAS 3.6 and will be removed in the next major version. Prefer an external DHCP server for this option when you can. See [Manage network services](manage-network-services.md) and [ONIE: Add a Remote Syslog Server](https://opencomputeproject.github.io/onie/user-guide/index.html#add-a-remote-syslog-server).

### Typical custom installer workflow

1. Build or prepare a wrapped image that ONIE can execute.

2. Upload the wrapped image:

   ```bash
   SHA256=$(sha256sum /path/to/wrapped-installer.bin | awk '{print $1}')
   curl -X POST "http://<maas-server>:5248/MAAS/a/v3/custom_images" \
     -H "Authorization: Bearer <api-token>" \
     -H "Content-Type: application/octet-stream" \
     -H "name: onie/mellanox-wrapper-3.8.0" \
     -H "architecture: amd64/generic" \
     -H "file-type: self-extracting" \
     -H "sha256: $SHA256" \
     -H "title: Mellanox wrapped installer 3.8.0" \
     --data-binary "@/path/to/wrapped-installer.bin"
   ```

3. Register the switch and assign the wrapped image:

   ```bash
   curl -X POST "http://<maas-server>:5248/MAAS/a/v3/switches" \
     -H "Authorization: Bearer <api-token>" \
     -H "Content-Type: application/json" \
     -d '{
       "mac_address": "00:11:22:33:44:55",
       "image": "mellanox-wrapper-3.8.0"
     }'
   ```

4. Power on the switch in ONIE mode. MAAS serves the wrapped image and your script performs the installation.

## Troubleshooting

### Switch doesn't receive installer URL

**Check network connectivity:**

- Verify the switch's management interface is connected to a network where MAAS provides DHCP
- Confirm DHCP is enabled on the appropriate subnet in MAAS

**Check switch registration:**

```bash
curl -X GET "http://<maas-server>:5248/MAAS/a/v3/switches" \
  -H "Authorization: Bearer <api-token>"
```

💡 MAAS automatically configures DHCP for ONIE—if the switch isn't getting the installer URL, the issue is typically network connectivity or subnet configuration, not DHCP options.

### Installer not found error

**Verify the image is assigned:**

```bash
curl -X GET "http://<maas-server>:5248/MAAS/a/v3/switches/{switch_id}" \
  -H "Authorization: Bearer <api-token>"
```

**Check the boot resource exists:**

```bash
curl -X GET "http://<maas-server>:5248/MAAS/a/v3/custom_images" \
  -H "Authorization: Bearer <api-token>" | jq '.items[] | select(.name | startswith("onie/"))'
```

**Ensure the image file was downloaded:**

```bash
ls -lh /var/lib/maas/boot-resources/current/
```

### Switch may be using a different MAC address than expected

ONIE will generally use the switches base MAC address, which in some instances may differ from the management MAC adress printed on the switch.
It may be possible to find the correct MAC address by looking at [MAAS discoveries](../reference/cli-reference/discovery.md), which list unknown interfaces with MAC Address and their Vendors.
From there it is generally simple to select the correct MAC address that ONIE is using and create a switch with it.

### Wrong interface MAC registered

If you registered the wrong MAC address:

1. Delete the incorrect switch entry:

   ```bash
   curl -X DELETE "http://<maas-server>:5248/MAAS/a/v3/switches/{switch_id}" \
     -H "Authorization: Bearer <api-token>"
   ```

2. Create a new entry with the correct management interface MAC:
   ```bash
   curl -X POST "http://<maas-server>:5248/MAAS/a/v3/switches" \
     -H "Authorization: Bearer <api-token>" \
     -H "Content-Type: application/json" \
     -d '{
       "mac_address": "correct:mac:address:here:00:00",
       "image": "mellanox-3.8.0"
     }'
   ```

## Resources

- [ONIE Project Documentation](https://opencomputeproject.github.io/onie/)
- [ONIE: Add a Remote Syslog Server](https://opencomputeproject.github.io/onie/user-guide/index.html#add-a-remote-syslog-server)
- [MAAS Images](manage-images.md)
