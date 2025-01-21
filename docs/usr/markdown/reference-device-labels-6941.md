> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/labelling-devices-for-maas" target = "_blank">Let us know.</a>*

This page explains the basics of device labelling.

## Hypervisor tags

To add hypervisor tags to a device via the UI, use the following screen:

![Hypervisor Definition](https://discourse.maas.io/uploads/default/original/2X/d/d1c8e2674445045ee9c8c9f1d14f3fa413af9be8.png)

Tailor the core and RAM requirements to your specific environment.

If you prefer the CLI, use a command of the form:

```nohighlight
maas ${MAAS_PROFILE} tags create name=hypervisor \
...
```

## AMD UEFI KVMs

Isolate UEFI-enabled KVM virtual machines running on AMD servers. Streamline your hardware filtering for a smoother operation.

![AMD-based UEFI KVMs](https://discourse.maas.io/uploads/default/original/2X/a/adde5f51e396a3a2d2f70daad7787fe087723664.png)

To do this via the CLI:

```nohighlight
maas ${MAAS_PROFILE} tags create \
...
```

## NVME servers

Instantly tag servers sporting NVME controllers for high-speed data storage.

![NVME Servers](https://discourse.maas.io/uploads/default/original/2X/1/166cd775669610ba454b5f2883e7729b79770bd0.png)

CLI version:

```nohighlight
maas ${MAAS_PROFILE} tags create ...
```

## Mellanox ConnectX-5

Identify servers featuring the highly sought-after Mellanox ConnectX-5 network cards.

![ConnectX-5 NICs](https://discourse.maas.io/uploads/default/original/2X/3/34ed75cf40ded49ac5eb8d76467817b5618b11a9.png)

The CLI command is:

```nohighlight
maas ${MAAS_PROFILE} tags create \
...
```

## GPU passthrough

When you want to crunch graphical data on AMD processors, enable GPU passthrough for Nvidia Quadro K series GPUs.

![Nvidia Quadro K Series](https://discourse.maas.io/uploads/default/original/2X/3/3f258d7e98c0adc7b605b8d2846b76737d46a27e.png)

Using the CLI:

```nohighlight
maas ${MAAS_PROFILE} tags create \
...
```