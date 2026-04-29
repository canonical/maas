# Deploying MAAS: Best practices

Installing MAAS is straightforward: add the snap, run `maas init`, and you’re up and running. But if you’ve ever watched a seasoned MAAS operator set up a region or rack, you’ll notice they make different choices than someone new to the tool. This page collects those best practices — lessons learned in real deployments — to help you get off on the right foot.

## Plan before you install

* **Separate the roles**: For production, don’t run everything on one box. Put the **region controller** on a stable, well-resourced server. Use one or more **rack controllers** close to the machines they’ll serve. This separation gives you scale and fault tolerance.
* **Pick your OS version carefully**: MAAS is supported on specific Ubuntu LTS releases. Match your MAAS version to an LTS that will be supported for as long as you need it.
* **Size for growth**: A small test lab might run on a VM, but in production, give MAAS enough CPU, memory, and disk. Logs and images can grow quickly.

## Network architecture matters

* **Use a dedicated MAAS network**: Don’t mix your management VLAN with user traffic if you can avoid it. DHCP, PXE, and DNS are sensitive to noise and conflicts.
* **Think about upstream DNS**: Configure MAAS to point to a reliable external resolver, or better, an internal recursive DNS. This reduces troubleshooting later.
* **Reserve ranges for MAAS**: Make sure DHCP ranges don’t overlap with statically assigned addresses. Carve out space for dynamic ranges, static IPs, and VIPs.
* **Enable HA where it counts**: Run multiple rack controllers in large environments. That way, DHCP/TFTP isn’t a single point of failure.

## Images and commissioning

* **Mirror close to your machines**: If possible, run a local image mirror. This avoids pulling large images across the internet and speeds up commissioning.
* **Keep your image catalog lean**: Don’t enable every Ubuntu release under the sun. Stick to the versions you actually deploy. Fewer images mean faster syncs.
* **Customize early if needed**: If you’ll need custom images (kernels, cloud-init hooks, drivers), build them up front and test them in a staging environment.

## Operating practices

* **Automate with the CLI and API**: The web UI is great for exploration, but serious deployments use `maas` CLI or API calls for repeatability. Keep scripts under version control.
* **Tag and group your machines**: Don’t leave hardware unorganized. Use tags, resource pools, and machine names that reflect purpose and role. It saves you later headaches.
* **Track power drivers**: Use the right power type for your hardware (IPMI, Redfish, etc.). Test each machine’s power cycling early, so you’re not surprised during deployment.
* **Audit your logs**: MAAS keeps detailed logs of events, DHCP, and commissioning. Learn where they live (`journalctl`, MAAS event logs) and check them regularly.

## Keep production and test separate

* **Run a test MAAS**: If you want to experiment with new versions or workflows, spin up a sandbox instance. Don’t risk your production environment with trial-and-error.
* **Stagger upgrades**: When upgrading MAAS, upgrade a non-critical instance first. Make sure your automation and integrations still work before touching production.

## The expert mindset

* **Treat MAAS as infrastructure plumbing**: Keep it stable, clean, and predictable.
* **Automate everything you can**: Manual clicks in the web UI don’t scale.
* **Document your conventions**: Future you (and your teammates) will thank you.
* **Expect to debug networks**: Many “MAAS issues” turn out to be VLANs, DNS, or DHCP conflicts. Have a mental model for packet flow before you start.

## Bottom line

Anyone can follow the quick-start guide and get MAAS running. The difference between a test install and a production-grade deployment is in the details: network planning, separation of roles, automation, and disciplined operating practices. Think like an infrastructure engineer, not just a software installer, and MAAS will serve you reliably at scale.
