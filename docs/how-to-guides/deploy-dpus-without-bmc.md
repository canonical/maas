# Deploy DPUs without BMC

With MAAS 3.3, we've made it possible to deploy workloads to DPUs. A DPU is a Data Processing Unit, which consists of its own set of ARM cores that can be used to offload data processing from the main host. We've tested it with a NVIDIA Bluefield-2 DPU, and here you will find instructions for how to get started deploying workloads to such a DPU.

## Initial setup

This guide assumes that the DPU host machine is not yet enlisted into MAAS. Before we enlist it, we're going to do a one-time setup to make things easier.

This guide assumes that you have a `maas` CLI profile called `admin`. If you don't, create one with:

```shell
sudo snap install maas
maas login admin $maas_url $api_token
```

### Tags

To make it easier to see which machines are DPUs and which are DPU hosts, we're going to set up a couple of [automatic tags](https://maas.io/docs/how-to-work-with-tags#heading--automatic-tags):

```shell
maas admin tags create name=dpu \
      definition='//node[@class="system"]//configuration/setting/@value="BlueField"'
maas admin tags create name=dpu-host \
      definition='//node[@class="generic"]/product = "MT42822 BlueField-2 SoC Management Interface"'
```

This makes sure that any machine in MAAS that is a Bluefield-2 DPU has the `dpu` tag, and any machine that contains a Bluefield-2 DPU has the `dpu-host` tag.

### Commissioning image

In order for all the hardware to be detected properly, we need to use Ubuntu 22.04 as the commissioning image. Ensure that's the case with this command:

```shell
maas admin maas set-config name=name=commissioning_distro_series value=jammy
```

### Deploy image

The Bluefield-2 DPU needs a special kernel and drivers for the network interfaces to work. We'll build a custom Ubuntu image with the necessary kernel and drivers, which we can use when deploying workloads to the DPU. We'll include a subset of what's in the [image that NVIDIA provides](https://github.com/Mellanox/bfb-build/blob/master/ubuntu/20.04/Dockerfile).

Please follow the [setup instructions for packer-maas](https://github.com/canonical/packer-maas/tree/main/ubuntu). Next we'll create a script that installs the bluefield related kernel and runtime packages:

```shell
cat <<EOF > setup-bluefield.sh
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
wget -qO - https://linux.mellanox.com/public/repo/doca/1.3.0/ubuntu20.04/aarch64/GPG-KEY-Mellanox.pub | apt-key add -
echo "deb [trusted=yes] https://linux.mellanox.com/public/repo/doca/1.3.0/ubuntu20.04/\$(ARCH) ./" | tee /etc/apt/sources.list.d/doca.list
apt-get update
apt-get install -y -f \
	linux-bluefield=5.4.0.1035.36 \
	linux-bluefield-headers-5.4.0-1035=5.4.0-1035.38 \
	linux-bluefield-tools-5.4.0-1035=5.4.0-1035.38 \
	linux-headers-5.4.0-1035-bluefield=5.4.0-1035.38 \
	linux-headers-bluefield=5.4.0.1035.36 \
	linux-image-5.4.0-1035-bluefield=5.4.0-1035.38 \
	linux-image-bluefield=5.4.0.1035.36 \
	linux-modules-5.4.0-1035-bluefield=5.4.0-1035.38 \
	linux-tools-5.4.0-1035-bluefield=5.4.0-1035.38 \
	linux-tools-bluefield=5.4.0.1035.36 \
	linux-libc-dev:arm64 \
	linux-tools-common \
	mlnx-ofed-kernel-modules \
	doca-libs \
	doca-runtime

apt-mark hold linux-tools-bluefield linux-image-bluefield linux-bluefield \
	linux-headers-bluefield linux-image-bluefield linux-libc-dev \
	linux-tools-common mlnx-ofed-kernel-modules doca-libs doca-runtime

mkdir -p /curtin
echo -n "linux-bluefield=5.4.0.1035.36" > /curtin/CUSTOM_KERNEL
EOF
```

Now we can build the package and upload it to MAAS:

```shell
sudo packer build -var customize_script=setup-bluefield.sh \
      -var ubuntu_series=focal -var architecture=arm64 \
      -only 'cloudimg.*'

maas admin boot-resources create name="custom/ubuntu-bluefield" \
      title="Ubuntu 20.04 LTS (bluefield 5.4.0.1035.36)" \
      architecture=arm64/generic filetype=tgz content@=custom-cloudimg.tar.gz
```

## Enlist host and DPU

Now when everything is set up, it's time to enlist both the host and DPU into MAAS. We assume here that the host is connected to a VLAN where MAAS is providing DHCP.

Now, use your favourite IPMI tool to set PXE for the next boot and turn on the host. For example:

```shell
ipmitool -H $bmc_ip -I lanplus -U $bmc_user -P $bmc_pass chassis bootdev pxe
ipmitool -H $bmc_ip -I lanplus -U $bmc_user -P $bmc_pass chassis power on
```

There should now be a new machine enlisted in MAAS as `NEW`. Let's rename it to `dpu-host` to keep track of it.

The DPU didn't yet get enlisted, since it's most likely  configured to boot from local disk and not from the network. We need to change the boot order. If the DPU is running Ubuntu already and you know how to access it, you can change the boot order using `efibootmgr`.

If not, let's deploy the host, so that we can access the DPU through it using RSHIM:

```shell
HOSTID=$(maas admin machines read hostname=dpu-host | jq '.[] | .system_id' | tr -d '"')
maas admin machine deploy $HOSTID osystem=ubuntu distro_series=jammy
```

When the host has finished deploying, ssh to the host and install RSHIM:

```shell
HOSTIP=$(maas admin machine read $HOSTID | jq '.ip_addresses[0]' | tr -d '"')
ssh ubuntu@$HOSTIP
ubuntu@dpu-host $ wget https://content.mellanox.com/BlueField/RSHIM/rshim_2.0.6-9.g7267006_amd64.deb
ubuntu@dpu-host $ sudo dpkg -i ./rshim_2.0.6-9.g7267006_amd64.deb
```

Now RSHIM is running and you can access the console of the DPU trough `/dev/rshim0/console`. Before you access the console, reboot the DPU by sending `SW_RESET 1` to `/dev/rshim0/misc`:

```shell
ubuntu@dpu-host $ sudo bash -c 'echo "SW_RESET 1" > /dev/rshim0/misc'
ubuntu@dpu-host $ sudo screen /dev/rshim0/console
```

Now when the DPU is starting up, press Escape 3 times when prompted. You're now in the boot manager menu and can select the boot order via `Boot Maintenance Manager` → `Boot Options` → `Change Boot Order`

When you exit, the DPU should restart and you can see it booting off the network. After a while you should see a new machine in MAAS with the `dpu` tag. Let's rename it to `dpu` for the sake of this guide.

You also need to set the power configuration to Manual, unless your DPU has a BMC.

## Power management

When working with a DPU, especially one without a BMC, it's important to know that the DPU's power is tightly coupled with the host power. If the host gets turned off, so does the DPU. This works both ways: if the host turns on, so does the DPU.

We set the power type to `Manual` for the DPU, since our DPU doesn't have a BMC. Instead, we're going to make use of the host to control the DPU power. Whenever we need to turn on the DPU, we instead turn on the host.

There are two ways we can do this, depending on the state of the host. If the host is `Deployed`, we can power cycle the host:

```shell
maas admin machine power-off $HOSTID
maas admin machine power-on $HOSTID
```

Note that when power cycling the host, we need to do a hard power cycle. If you do a soft power cycle (e.g. by running `reboot` from within the host), the DPU won't be power-cycled.

If the host is in a `Ready` state, we can instead commission the host to turn it on. Note, though, that we need to select `Allow SSH access and prevent machine powering off` when doing so. Otherwise, the host would turn off at the end of the commissioning process, which might occur before the DPU has finished doing its work:

```shell
maas admin machine commission $HOSTID enable_ssh=true
```

You can try it out by choosing to commission the DPU now and issue the `power-off` and `power-on` commands. You should then see the DPU being commissioned and put into a `Ready` state.

## Deploying workloads

Now you're ready to deploy workloads to the DPU and the host. We're not going to tell you in what ways you can configure the DPU and interact with it from the host. Rather we're going to go over how you deploy Ubuntu to it. It's up to you to choose workloads that you want to run and configure.

You can easily deploy a workload to the DPU and host, in pretty much the same way you deploy a workload to a regular machine – with the caveat that you need to manually power cycle the DPU after you tell MAAS to deploy it.

Also, remember that you need the custom image for the DPU that we created and uploaded in the beginning of this guide:

```shell
DPUID=$(maas admin machines read hostname=dpu | jq '.[] | .system_id' | tr -d '"')
maas admin machine deploy $DPUID osystem=custom distro_series=ubuntu-bluefield
```

And now, if you power cycle the DPU, you should see it deploying.

## Host and DPU dependencies

As mentioned before, the host is tightly coupled with the DPU. It's advised that you first deploy the DPU and configure it as much as you can. After that, it might even be required to recommission the host, since it might see other network interfaces, depending on how you configured the DPU.

In general, the host should be deployed after the DPU has been deployed and configured, since the host might rely on a specific DPU configuration.
