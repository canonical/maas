> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/troubleshooting-common-maas-issues" target = "_blank">Let us know.</a>*

## MAAS OS deployment failing with cloud-init error

**Problem:**
Deployment of a JUJU controller or an OS directly on a node fails with the error "cloud-init Data source not found."

**Environment:**
- MAAS version: stable (2.8 mentioned)
- Single NIC for MAAS node and JUJU controller node
- Ubuntu 16.04 and 18.04 tried

**Potential causes and solutions:**

1. **Cloud-init unable to reach MAAS metadata server:**
   - Ensure that the nodes can reach the MAAS metadata server, which provides SSH keys and user_data.

   **Solution:**
   - Verify that the DNS server in your environment is set to the MAAS region/rack controller IP. You can set this in the Subnet Summary under the MAAS UI.
   - Ensure that "Allow DNS resolution" is enabled and correctly configured with the MAAS server's IP.
   
   ```bash
   maas $profile subnet update $subnet_id dns_servers="[$MAAS_IP]"
   ```

2. **MAAS services or proxy issues:**
   - Issues with services like squid or bind could also lead to this problem. Sometimes toggling the proxy settings can help.

   **Solution:**
   - Toggle the proxy configuration from 'Don’t use a proxy' to 'MAAS built-in' or vice versa.

   ```bash
   maas $profile maas set-config name=http_proxy value="http://proxy.example.com:8000/"
   maas $profile maas set-config name=http_proxy value=""
   ```

3. **Network configuration and connectivity:**
   - The network setup should ensure proper routing and availability of the MAAS metadata service.

   **Solution:**
   - Check network configurations and ensure there are no firewalls or network issues blocking access to the MAAS server.

4. **Restarting MAAS services:**
   - Sometimes, simply restarting the MAAS services can resolve intermittent issues.

   **Solution:**
   - Restart MAAS services:

   ```bash
   sudo systemctl restart maas-rackd maas-regiond
   ```

5. **BIOS configuration:**
   - There might be differences in BIOS configurations that affect deployment.

   **Solution:**
   - Ensure that BIOS settings, especially related to network boot and BMCs, are consistent and correctly configured.

6. **Check subnet and IP configuration:**
   - Ensure the IP configuration for subnets is correct, and no conflicting, overlapping or duplicate subnets are present.

   **Solution:**
   - Verify and correct subnet configurations in the MAAS UI.

7. **Log analysis:**
   - Detailed logs can provide more insights into the issue.

   **Solution:**
   - Check MAAS and cloud-init logs for more details using the instructions provided in the [logging documentation](/t/how-to-use-maas-systemd-logs/8103/).

### Example configuration and commands:

```bash
# Ensure DNS is correctly set
maas admin subnet update $subnet_id dns_servers="[$MAAS_IP]"

# Restart MAAS services
sudo systemctl restart maas-rackd maas-regiond

# Check MAAS logs
# insert relevant commands here
```

### Community tips:

- Adding a dynamic reserved range to the IPv6 subnet helped one user resolve the issue.
- Ensuring the DNS IP in the subnet summary is set to the MAAS region/rack servers' IP.

By following these steps and checking these configurations, you should be able to resolve the "cloud-init Data source not found" error and successfully deploy your OS using MAAS.

## Decoupling DNS from MAAS and resolving configuration issues

**Problem:**
MAAS restarted after an update, causing DNS to fail due to duplicate subnets and configurations. This led to BIND9 failing to start, creating repeated crashes and restarts of the DNS service.

**Solution:**

### Steps to decouple DNS from MAAS and resolve configuration issues:

1. **Identify the issue:**
   - The issue was identified by errors in the [MAAS log files](/t/how-to-use-maas-systemd-logs/8103/), indicating problems with BIND9 due to duplicate subnets.

2. **Check for duplicate subnets:**
   - Run the following command to list all subnets and identify duplicates:
     ```bash
     maas $profile subnets read
     ```

3. **Remove duplicate subnets:**
   - Identify any duplicate subnets in the output. Pay special attention to subnets with odd subnet masks or those that appear more than once.
   - Remove the duplicate subnets using the MAAS CLI or web interface:
     ```bash
     maas $profile subnet delete $subnet_id
     ```

4. **Restart MAAS services:**
   - After removing the duplicate subnets, restart the MAAS services to apply the changes:
     ```bash
     sudo systemctl restart maas-regiond maas-rackd
     ```

5. **Verify DNS configuration:**
   - Check the DNS configuration files to ensure there are no remaining issues. The relevant files can be found in:
     ```bash
     # deb
     /etc/bind/maas/

     # snap
     /var/snap/maas/current/bind/
     ```

6. **Decouple DNS from MAAS:**
   - If you wish to decouple DNS entirely from MAAS and use an external DNS server, you can disable the MAAS-managed DNS service:
     ```bash
     sudo maas $profile dns update 1 enabled=false
     ```
   - Configure your external DNS server to handle all DNS queries.

### Example Commands:
```bash
# List all subnets to find duplicates
maas admin subnets read

# Delete a problematic subnet (replace $subnet_id with the actual ID)
maas admin subnet delete $subnet_id

# Restart MAAS services to apply changes
sudo systemctl restart maas-regiond maas-rackd

# Disable MAAS-managed DNS
sudo maas admin dns update 1 enabled=false
```

### Verification:
- Ensure the DNS service is running smoothly without errors.
- Verify that the external DNS server is correctly configured and resolving queries.

By following these steps, you can decouple DNS from MAAS, resolve configuration issues, and ensure a stable DNS environment for your OpenStack cluster and other services.

## Configuring the second NIC for external DHCP in MAAS

**Problem:**
You have managed to deploy machines with two NICs using MAAS. The first NIC uses PXE/DHCP, but configuring the second NIC to use external DHCP is proving challenging.

**Solution:**

### Steps to configure the second NIC for external DHCP:

1. **Commission the machine:**
   - Ensure the machine is commissioned in MAAS. After commissioning, MAAS should recognize both NICs.

2. **Check interface status:**
   - Verify if the second interface shows as connected to the correct VLAN/subnet from the external DHCP server.

3. **Configure the second NIC:**
   - Navigate to the machine details page in the MAAS UI.
   - Go to the "Network" tab to see the list of network interfaces.
   - Find the second NIC (e.g., `eth1` or `ens19`).

4. **Set interface to DHCP:**
   - Edit the configuration of the second NIC.
   - Set the interface to "DHCP" to ensure it will acquire an IP address from the external DHCP server. This is different from "Auto assign," where MAAS would assign an IP before deployment.

### Detailed steps in the MAAS UI:

1. **Access machine details:**
   - Go to the "Machines" tab.
   - Click on the specific machine you are configuring.

2. **Navigate to network interfaces:**
   - In the machine details page, click on the "Network" tab.

3. **Edit the second NIC configuration:**
   - Locate the second NIC (e.g., `eth1` or `ens19`).
   - Click on the pencil icon (edit) next to the interface.

4. **Set to DHCP:**
   - In the configuration dialog, select "DHCP" from the dropdown menu.
   - Save the changes.

### Verify configuration:

1. **Deploy the machine:**
   - Deploy the machine from MAAS.
   - Ensure it successfully boots and the second NIC acquires an IP address from the external DHCP server.

2. **Check network configuration:**
   - SSH into the deployed machine.
   - Use `ip a` or `ifconfig` to check if the second NIC has acquired an IP address from the external DHCP server.

```bash
ip a
```

3. **Troubleshoot if necessary:**
   - If the second NIC does not acquire an IP address, check the DHCP server configuration and ensure it is correctly set up to provide IP addresses on the intended subnet.

By following these steps, you should be able to configure the second NIC on a machine deployed with MAAS to use an external DHCP server for IP address allocation.

## MAAS setup with existing/external DHCP

**Problem:**
A user was trying to set up MAAS with an existing DHCP server on an Edgerouter 12. However, when attempting to PXE boot machines, they received a 'no media found' error. The goal was to use MAAS without creating VLANs or replacing the existing DHCP server.

**Solution:**

### Summary:
The user ultimately resolved the issue by disabling the router's DHCP and using the built-in DHCP service in MAAS.

### Detailed steps to configure MAAS with an existing DHCP server:

1. **Understand MAAS DHCP configuration:**
   - By default, MAAS manages DHCP for PXE booting. However, it is possible to integrate with an existing DHCP server.

2. **MAAS configuration:**
   - **Disable MAAS DHCP:** Since the existing DHCP server on the router will handle IP allocation, you need to disable the MAAS DHCP server.
   - **Configure ProxyDHCP:** MAAS can function with ProxyDHCP to handle PXE boot requests without managing the IP allocation.

3. **Existing DHCP server configuration:**
   - **Add DHCP options for PXE booting:**
     - Configure the existing DHCP server to include options for booting via PXE. You need to add the following options:
       - **Option 66 (next-server):** IP address of the MAAS server.
       - **Option 67 (filename):** Path to the bootloader, typically something like `pxelinux.0`.

   Example DHCP configuration for PXE boot:

   ```plaintext
   dhcp-option=66, "192.168.1.100"  # IP address of the MAAS server
   dhcp-option=67, "pxelinux.0"     # Bootloader file
   ```

4. **Check MAAS DHCP configuration:**
   - If you need to reference the configuration MAAS would generate, you can find it in `/var/snap/maas/common/maas/dhcpd.conf` for a snap installation.

5. **Test PXE boot:**
   - Ensure that the client machines are set to PXE boot from the network.
   - Reboot the machines and verify if they receive the PXE boot instructions from the existing DHCP server and proceed with commissioning and deployment via MAAS.

### Additional considerations:
- **Network configuration:**
  - Ensure that the MAAS server and the existing DHCP server are on the same network segment to avoid any routing issues.
- **Debugging:**
  - Use network tools like `tcpdump` or Wireshark to capture DHCP and TFTP traffic to troubleshoot any issues with PXE booting.

### Final solution:
If integrating with the existing DHCP server proves too challenging or unreliable, consider using the built-in DHCP service in MAAS as Robert-datacare eventually did. This approach simplifies the setup and leverages MAAS's full capabilities for managing DHCP, DNS, and PXE booting seamlessly.

By following these steps, you can configure MAAS to work with an existing DHCP server or switch to using the built-in MAAS DHCP service to manage network booting and machine provisioning effectively.

## Configuring multiple NICs on a machine with MAAS

**Problem:**
You want to configure a machine with two NICs. NIC #1 is connected to a private subnet managed by MAAS, while NIC #2 is connected to a public subnet used for internet access. The user struggled to find a way to configure NIC #2 through the MAAS UI.

**Solution:**

Yes, it is possible to have two NICs working on a machine in MAAS. Here's how you can configure both NICs:

1. **Ensure both NICs are detected:**
   - Verify that both NICs are detected by MAAS. You should see both interfaces (ens18 and ens19) in the MAAS UI under the machine's network configuration.

2. **Edit network configuration in MAAS:**
   - Go to the MAAS UI.
   - Select the machine in question.
   - Navigate to the "Network" tab.
   - For NIC #1 (ens18):
     - Ensure it is configured to use DHCP on the private subnet (192.168.10.0/24).
   - For NIC #2 (ens19):
     - Edit the interface settings to configure it manually for the public subnet (192.168.1.0/24).

3. **Configure NIC #2 manually in MAAS:**
   - In the "Edit Physical" mask for ens19, select the appropriate fabric and subnet (public subnet 192.168.1.0/24).
   - Set the IP address manually or configure it to use DHCP if your public network has a DHCP server.
   - Assign the gateway and DNS settings as needed for internet access.

4. **Example netplan configuration:**
   - Ensure that the netplan configuration reflects the settings from MAAS. Here is an example of how the `50-cloud-init.yaml` might look:

     ```yaml
     network:
         version: 2
         ethernets:
             ens18:
                 addresses:
                 - 192.168.10.5/24
                 match:
                     macaddress: 8e:57:8a:55:d4:2d
                 mtu: 1500
                 nameservers:
                     addresses:
                     - 192.168.10.10
                     search:
                     - maas
                 set-name: ens18
             ens19:
                 addresses:
                 - 192.168.1.10/24  # Set this according to your network
                 gateway4: 192.168.1.1  # Default gateway for internet access
                 nameservers:
                     addresses:
                     - 8.8.8.8  # Google's DNS or your preferred DNS
                     - 8.8.4.4
                 match:
                     macaddress: c6:11:fb:c9:5e:e2
                 mtu: 1500
                 set-name: ens19
     ```

5. **Apply the configuration:**
   - Apply the network configuration using the `netplan apply` command or reboot the machine to ensure the settings take effect.

**Note:**
There was a mention of a bug when selecting a Fabric in the "Edit Physical" mask, causing it to jump back. Ensure that the correct fabric and subnet are selected before saving the configuration.

By following these steps, you should be able to configure both NICs on your machine, allowing it to communicate on both the private MAAS-managed network and the public internet-facing network.

## Manual DHCP Allocation with MAAS

**Problem:**
A casual user is considering using MAAS for his homelab, primarily for learning configuration and deployment of containers on Raspberry Pi clusters. He has traditionally used manual DHCP allocations for server IP addresses to simplify IP address management and DNS. He is concerned whether this approach will conflict with MAAS's use of DHCP.

**Solution:**

You can use manual DHCP allocations with MAAS, but you need to ensure that the DHCP offers set the next-server address to the TFTP boot server. This is crucial as it allows MAAS machines (such as your Raspberry Pi clusters) to get the address of boot servers to request a Network Boot Program (NBP).

**Steps:**

1. **Configure DHCP server:**
   - Ensure your DHCP server is configured to assign static IP addresses based on MAC addresses for your Raspberry Pi clusters.
   - Set the `next-server` option in your DHCP server configuration to point to the MAAS TFTP server.

   Example DHCP configuration snippet:
   ```bash
   host raspberrypi1 {
       hardware ethernet xx:xx:xx:xx:xx:xx;
       fixed-address 192.168.1.10;
       next-server 192.168.1.2;  # IP address of the MAAS TFTP server
       filename "pxelinux.0";    # Or the appropriate boot file for your environment
   }
   ```

2. **Ensure proper MAAS configuration:**
   - In the MAAS UI, navigate to the 'Subnets' section and make sure your subnet is correctly configured.
   - Ensure that MAAS is set to manage DHCP for the subnet in question, but remember that your manual DHCP assignments will take precedence for the specified MAC addresses.

3. **Testing:**
   - Boot one of your Raspberry Pi devices and check that it receives the correct IP address and can locate the MAAS TFTP server to start the network boot process.

4. **Managing IP address assignments:**
   - Keep track of your manual DHCP assignments to avoid conflicts. Ensure all devices have unique IP addresses.
   - Use MAAS’s interface to monitor and manage DHCP leases and static assignments.

By following these steps, you can integrate manual DHCP allocations with MAAS, maintaining your existing IP address management strategy while leveraging MAAS's powerful provisioning capabilities.

## DHCP services stopped working

**Problem:**
MAAS 2.9.2 (snap) DHCP services stopped working after memory and disk issues were resolved. Despite fixing the memory and disk problems and rebooting, the DHCP services are not starting.

**Solution:**

1. **Check logs:**
   - Look into the [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/).
   - The error log shows something like this:
     ```
     2021-06-09 08:58:43 maasserver.rack_controller: [critical] Failed configuring DHCP on rack controller 'id:1'.
       File "/snap/maas/12555/lib/python3.8/site-packages/maasserver/dhcp.py", line 864, in configure_dhcp
         config = yield deferToDatabase(get_dhcp_configuration, rack_controller)
       File "/snap/maas/12555/lib/python3.8/site-packages/maasserver/dhcp.py", line 783, in get_dhcp_configuration
         config = get_dhcp_configure_for(
       File "/snap/maas/12555/lib/python3.8/site-packages/maasserver/dhcp.py", line 663, in get_dhcp_configure_for
       File "/snap/maas/12555/lib/python3.8/site-packages/maasserver/dhcp.py", line 444, in make_subnet_config
       File "/snap/maas/12555/lib/python3.8/site-packages/maasserver/dhcp.py", line 447, in <listcomp>
     ```

2. **Check for configuration corruption:**
   - The issues might be caused by configuration corruption due to previous memory and disk issues.

3. **Verify subnet and fabric configuration:**
   - Go to the MAAS UI and check if the subnets are assigned to the correct fabrics.
   - If a subnet appears under the wrong fabric, reassign it to the correct fabric.

     Steps:
     - Navigate to the "Subnets" section.
     - Open the subnet configuration page.
     - Reassign the subnet to the correct fabric.
   
4. **Restart MAAS services:**
   - After correcting the subnet assignment, restart the MAAS services.

   ```bash
   sudo systemctl restart maas-rackd
   sudo systemctl restart maas-regiond
   ```

5. **Cleaning up proxy cache (if applicable):**
   - If using a proxy, sometimes cleaning the proxy cache can resolve issues.

   ```bash
   sudo mv /var/snap/maas/common/proxy /var/snap/maas/common/proxy.old
   sudo mkdir -p /var/snap/maas/common/proxy
   sudo chown -R proxy:proxy /var/snap/maas/common/proxy
   sudo chmod -R 0750 /var/snap/maas/common/proxy
   sudo systemctl restart maas-proxy
   ```

6. **Verify DHCP settings:**
   - Ensure that the DHCP settings are correct in the MAAS UI.
   - Verify that DHCP is enabled on the correct subnets.

7. **Check and repair database:**
   - Sometimes issues may be related to the MAAS database. Verify the database integrity and repair if necessary.

   ```bash
   sudo maas-region dbshell
   # Inside the database shell
   VACUUM FULL;
   ```

By following these steps, you should be able to diagnose and resolve the issues preventing the DHCP services from starting in MAAS.

## Setting up an upstream DNS for external DNS resolution in MAAS

**Problem:**
You have set up a MAAS environment with DHCP and DNS enabled. However, your MAAS-deployed devices are unable to resolve hostnames using upstream DNS. Specifically, you are trying to resolve the hostname "grafana" but it only resolves via IP.

**Solution:**

1. **Verify upstream DNS configuration:**
   Ensure that your MAAS configuration includes the correct upstream DNS servers. You can set this up in the MAAS UI or via the command line.

2. **Edit DNS configuration in MAAS:**
   - Go to the MAAS UI.
   - Navigate to the “Settings” tab.
   - Under the "DNS" section, add your upstream DNS servers.

3. **Verify /etc/netplan configuration:**
   Ensure that the `netplan` configuration on your MAAS-deployed device points to the correct DNS servers.

   ```yaml
   network:
     version: 2
     ethernets:
       enp1s0:
         dhcp4: no
         addresses:
           - 192.168.178.139/24
         gateway4: 192.168.178.1
         nameservers:
           search:
             - maas
           addresses:
             - 192.168.178.70
             - 192.168.178.1
   ```

4. **Check systemd-resolved configuration:**
   Verify that `systemd-resolved` is correctly configured to use the upstream DNS servers.

   ```bash
   sudo systemctl restart systemd-resolved
   sudo systemctl status systemd-resolved
   ```

   Ensure that `/etc/resolv.conf` is correctly linked to `systemd-resolved`.

   ```bash
   sudo ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
   ```

5. **Test DNS resolution:**
   Use the `dig` command to test DNS resolution directly against your upstream DNS.

   ```bash
   dig @192.168.178.70 grafana
   dig @192.168.178.1 grafana
   ```

6. **Check MAAS DHCP and DNS configuration:**
   Ensure that MAAS is correctly configured to provide the right DNS settings to its deployed devices.

   ```bash
   sudo maas <profile> dhcp-snippet read 0
   ```

7. **Restart network services:**
   Restart network services on your MAAS-deployed device to apply changes.

   ```bash
   sudo netplan apply
   sudo systemctl restart systemd-networkd
   ```

8. **Update DNS search domain:**
   Ensure that the search domain includes the external domain if needed.

   ```bash
   sudo nano /etc/systemd/resolved.conf
   # Add or update the DNS and Domains entries
   [Resolve]
   DNS=192.168.178.70 192.168.178.1
   Domains=maas
   ```

   Restart `systemd-resolved` again.

   ```bash
   sudo systemctl restart systemd-resolved
   ```

By following these steps, your MAAS-deployed devices should be able to resolve hostnames using the upstream DNS servers.

## Unable to commission server - cloud-init error: "Can not apply stage final, no datasource found!"

**Problem:**
You are experiencing an issue where newly commissioned servers in your MAAS 3.1 environment fail with the cloud-init error "Can not apply stage final, no datasource found!" This problem is preventing you from commissioning new servers while your existing OpenStack environment has been running properly for some time.

**Solution:**

1. **Verify network configuration:**
   - Ensure that the network configuration for the new servers is correct. Check that the servers can reach the MAAS server and that there are no network issues preventing them from accessing the necessary metadata.

   ```bash
   # Check network interfaces
   ip a
   # Check routing
   ip route
   # Check DNS resolution
   nslookup maas-server-ip
   ```

2. **Check MAAS logs:**
   - Review the [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/) for any errors or warnings that might provide more context about the issue.

3. **Verify cloud-init configuration:**
   - Ensure that the cloud-init configuration is correct and that the datasource is properly defined. This is crucial for the commissioning process.

4. **Update cloud-init configuration:**
   - Sometimes, updating the cloud-init configuration can resolve issues with datasource detection. Edit the `/etc/cloud/cloud.cfg` file to ensure the datasource is correctly specified.

   ```bash
   # Edit the cloud-init configuration file
   sudo nano /etc/cloud/cloud.cfg

   # Ensure the datasource list includes MAAS
   datasources:
     - MAAS
   ```

5. **Recommission the server:**
   - After verifying and updating the configurations, recommission the server through the MAAS UI or CLI.

   ```bash
   # Recommission the server via CLI
   maas $PROFILE machine commission $SYSTEM_ID
   ```

6. **Reset the node:**
   - If the issue persists, try resetting the node and recommissioning it. This can often resolve issues related to temporary network or configuration glitches.

   ```bash
   # Reset the node via CLI
   maas $PROFILE machine release $SYSTEM_ID
   maas $PROFILE machine commission $SYSTEM_ID
   ```

7. **Update MAAS and cloud-init:**
   - Ensure that you are running the latest version of MAAS and cloud-init, as updates often include bug fixes and improvements.

   ```bash
   # Update MAAS
   sudo snap refresh maas

   # Update cloud-init
   sudo apt-get update
   sudo apt-get install --only-upgrade cloud-init
   ```

8. **Consult documentation and community:**
   - If you continue to experience issues, refer to the official MAAS and cloud-init documentation for further troubleshooting steps. Additionally, consider reaching out to the MAAS community or support channels for more specific guidance.

By following these steps, you should be able to troubleshoot and resolve the issue preventing your servers from commissioning successfully in MAAS.

## DHCP service stops when network connection between region and racks is disconnected

**Problem:**
When the network connection between the MAAS region controller and rack controllers is interrupted, the DHCP services on the rack nodes stop, causing deployed machines to lose their IP addresses after the lease time expires. The issue resolves itself when the network hardware is rebooted.

**Solution:**

1. **Ensure network reliability:**
   - The MAAS architecture relies on constant communication between the region and rack controllers. Ensuring a stable and reliable network connection between these components is critical.
  
2. **Redundancy:**
   - Set up a secondary region controller to add redundancy. This might not solve the problem during a complete network outage but can help mitigate issues if a single region controller fails.

3. **Extend DHCP Lease Time:**
   - Extending the DHCP lease time can help mitigate the issue during brief network outages. This can be done using DHCP snippets to modify the lease duration in the MAAS DHCP configuration.

   **Steps to extend DHCP lease time:**
   - Create a DHCP snippet to extend the lease time.

   ```bash
   echo 'dhcp-lease-time 86400; # 1 day' | sudo tee /etc/maas/dhcpd.conf.d/lease-time.conf
   sudo systemctl restart maas-rackd
   sudo systemctl restart maas-regiond
   ```

4. **Use external DHCP servers:**
   - Configure external DHCP servers on each network segment. This ensures that even if the region controller is unreachable, machines can still obtain IP addresses.

   **Steps to configure external DHCP server:**
   - Set up ISC DHCP server on Ubuntu:

     ```bash
     sudo apt update
     sudo apt install isc-dhcp-server
     ```

   - Configure the DHCP server by editing `/etc/dhcp/dhcpd.conf`:

     ```bash
     subnet 192.168.1.0 netmask 255.255.255.0 {
       range 192.168.1.10 192.168.1.100;
       option routers 192.168.1.1;
       option domain-name-servers 8.8.8.8, 8.8.4.4;
     }
     ```

   - Restart the DHCP server:

     ```bash
     sudo systemctl restart isc-dhcp-server
     ```

   - Ensure that the DHCP server is detected by MAAS. Configure at least one node to use DHCP so that MAAS can recognize the external DHCP server.

5. **Network maintenance strategy:**
   - Plan network maintenance during off-peak hours and ensure it does not exceed the DHCP lease duration.
   - Implement network maintenance strategies that minimize the need for complete network downtime, such as using redundant paths or gradual network component replacements.

6. **Troubleshooting external dhcp server detection:**
   - Ensure that DHCP packets are being sent and received properly.
   - Check the MAAS Web UI under "Controllers" to verify if the external DHCP server is detected.

   **Steps to verify external DHCP server:**
   - Configure a node to use DHCP.
   - Check the MAAS Web UI under the "Controllers" section to see if the external DHCP server is listed.

   If the external DHCP server is not detected, verify the network configuration and ensure that DHCP packets are correctly being relayed to MAAS.

**Conclusion:**
By implementing redundancy, extending DHCP lease times, using external DHCP servers, and planning network maintenance effectively, you can ensure that DHCP services continue to function even during network disruptions.

## Problem with APT proxy

**Problem:**
Some machines encounter errors while commissioning, specifically failing to locate packages due to issues with the APT proxy in MAAS. The error appears as follows:

```
Reading package lists...
Building dependency tree...
Reading state information...
E: Unable to locate package lldpd
```

When entering rescue mode and manually running `apt update`, the error shows a connection failure to the APT proxy IP:

```
sudo apt update
Err:1 http://archive.ubuntu.com/ubuntu focal InRelease
  Connection failed [IP: 10.8.8.183 8000]
Hit:2 http://archive.ubuntu.com/ubuntu focal-updates InRelease
Hit:3 http://archive.ubuntu.com/ubuntu focal-security InRelease
Hit:4 http://archive.ubuntu.com/ubuntu focal-backports InRelease
```

Switching to an external proxy (standard HTTP proxy) resolves the issue, indicating a problem with the MAAS proxy.

**Solution:**

1. **Identifying the issue:**
   The error may be related to the Squid proxy on the MAAS node. Errors similar to:
   ```
   Err:4 http://archive.ubuntu.com/ubuntu focal InRelease
   Clearsigned file isn't valid, got 'NOSPLIT' (does the network require authentication?)
   ```

2. **Cleaning the proxy cache:**
   The issue can often be resolved by cleaning the Squid proxy cache on the MAAS node.

   **Steps to clean squid cache:**
   - Move the existing proxy cache directory to a backup location.
   - Create a new proxy cache directory.
   - Set appropriate ownership and permissions.
   - Restart the MAAS proxy service.

   **Commands:**
   ```bash
   sudo mv /var/spool/maas-proxy /var/spool/maas-proxy.old
   sudo mkdir -p /var/spool/maas-proxy
   sudo chown -R proxy:proxy /var/spool/maas-proxy
   sudo chmod -R 0750 /var/spool/maas-proxy
   sudo systemctl restart maas-proxy
   ```

   **Explanation:**
   - `sudo mv /var/spool/maas-proxy /var/spool/maas-proxy.old`: Moves the existing cache directory to a backup location.
   - `sudo mkdir -p /var/spool/maas-proxy`: Creates a new cache directory.
   - `sudo chown -R proxy:proxy /var/spool/maas-proxy`: Sets the ownership of the new cache directory to the proxy user.
   - `sudo chmod -R 0750 /var/spool/maas-proxy`: Sets the permissions for the cache directory.
   - `sudo systemctl restart maas-proxy`: Restarts the MAAS proxy service to apply changes.

3. **Confirmation:**
   After performing the above steps, verify if the commissioning process completes successfully without encountering the APT proxy errors.

**Conclusion:**
Cleaning the Squid proxy cache on the MAAS node has resolved similar issues for other users. If the issue persists, further investigation into network configurations or MAAS proxy settings may be required.

## Managed Allocation and Reserved Ranges, Auto-Assign

**Problem:**
Clarification needed on how MAAS handles IP address allocation in subnets, particularly concerning managed allocation, reserved ranges, dynamic ranges, and the difference between auto-assigned and DHCP-assigned IP addresses.

**Solution:**

1. **Managed allocation in subnets:**

   - **Managed allocation:**
     When managed allocation is enabled for a subnet, MAAS takes charge of assigning IP addresses. It uses specific ranges for different purposes.
     
     - **Dynamic range:**
       This is the range from which MAAS leases addresses for DHCP during commissioning or enlistment. MAAS DHCP server picks IPs from this range.
     
     - **Reserved range:**
       IP addresses within the reserved range are not assigned by MAAS. These ranges are set aside for infrastructure systems, network hardware, external DHCP, or other uses outside of MAAS’s automatic management.

   - **Unmanaged allocation:**
     If managed allocation is disabled, MAAS does not automatically assign IP addresses from the subnet.

2. **Explanation from documentation:**

   - **MAAS glossary and forum:**
     The glossary mentions that MAAS will not assign IPs inside the reserved range for managed subnets. The forum clarifies that during commissioning or enlistment, the dynamic range is used for DHCP leases, which means that nodes in these phases will get IPs from the dynamic range.

   - **Dynamic range usage:**
     Managed allocation uses the dynamic range for temporary leases during commissioning or enlistment but excludes these from auto-assignments for provisioned nodes. This ensures a clear separation between IPs used temporarily and those assigned for operational use.

3. **Auto-assigned vs. DHCP-Assigned IPs:**

   - **Auto-assigned IPs:**
     These IPs are automatically assigned by MAAS during the node provisioning process. These are typically static IPs allocated outside the reserved dynamic range.

   - **DHCP-assigned IPs:**
     Nodes can be configured to use DHCP, where they will obtain their IP addresses from the MAAS-managed dynamic range. This mode is useful for nodes that may need to change their IP addresses frequently or for short-lived operations.

**Steps to resolve:**

1. **Verify subnet configuration:**
   - Check the subnet settings in the MAAS UI to ensure managed allocation is enabled or disabled as needed.
   - Configure the dynamic and reserved ranges appropriately to match your network design.

2. **Understand IP allocation:**
   - Ensure that IP addresses required for temporary use (commissioning/enlistment) fall within the dynamic range.
   - Set aside reserved ranges for infrastructure and systems not managed by MAAS.

3. **Adjust node networking settings:**
   - For nodes requiring static IPs, use the auto-assign mode.
   - For nodes requiring dynamic IPs, configure them to use DHCP.

By clarifying these points, you should have a better understanding of how MAAS handles IP address allocation within subnets and the difference between auto-assigned and DHCP-assigned IP addresses.

For more detailed information, refer to the [MAAS documentation](https://maas.io/docs) and the [MAAS glossary](https://maas.io/docs/reference-maas-glossary) for explanations on IP ranges and allocation modes.

## Error: The server connection failed with the error “Bad Gateway”

**Problem:**
The MAAS UI was accessible until the network configuration was changed, putting it in its own network without an external DHCP. Now, the user gets an error: "Bad Gateway".

**Solution:**

1. **Verify Network configuration:**
   - Ensure that the MAAS server is correctly configured in its new network.
   - Check if the new IP address of the MAAS server is reachable.

2. **Check MAAS configuration:**
   - Since the IP address of the MAAS server was changed, update the MAAS configuration to reflect the new IP address:
     ```sh
     sudo maas config --maas-url=http://<new-ip-address>:5240/MAAS
     ```

3. **Check PostgreSQL connection:**
   - The error logs may show an issue with the PostgreSQL connection. Verify that PostgreSQL is running and accepting connections on the new IP address.
   - Update the PostgreSQL configuration to allow connections from the new IP address:
     ```sh
     sudo nano /etc/postgresql/12/main/pg_hba.conf
     ```
     - Add or update the line to allow connections:
       ```
       host all all <new-ip-address>/32 md5
       ```
     - Restart PostgreSQL:
       ```sh
       sudo systemctl restart postgresql
       ```

4. **Verify DHCP settings:**
   - Ensure that MAAS is configured to manage DHCP on the new network if needed:
     ```sh
     maas $PROFILE vlan update $FABRIC_ID $VLAN_TAG dhcp_on=True primary_rack=$PRIMARY_RACK_CONTROLLER
     ```

5. **Check logs for further issues:**
   - Review the [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/) for any additional errors.

6. **Restart MAAS services:**
   - Restart the MAAS services to apply the new configurations:
     ```sh
     sudo systemctl restart maas-regiond maas-rackd
     ```

7. **Validate networking configuration:**
   - Use the "Validate networking configuration" button in the MAAS UI or run the following command to ensure network settings are correct:
     ```sh
     maas $PROFILE subnet read $SUBNET_ID
     ```

By following these steps, you should be able to resolve the "Bad Gateway" error and restore access to the MAAS UI. If the issue persists, consider additional troubleshooting on the network level or consult the [MAAS documentation](https://maas.io/docs) for further guidance.

## Used IP addresses in a subnet empty even though DHCP leases are given out

**Problem:**
MAAS is sending out DHCP leases to both a BMC and a machine set to PXE boot, but the MAAS UI does not show any machines or used IP addresses in the subnet. This issue is hindering the auto-discovery and provisioning process.

**Solution:**

1. **Verify DHCP leases:**
   - Ensure that the DHCP leases are being given out correctly by checking the `dhcpd.leases` file in MAAS. You should see entries for both the BMC and the machine you're trying to PXE boot.

2. **Check network configuration:**
   - Confirm that the hosts are on a different subnet than MAAS and that a DHCP relay is configured correctly. Verify that the relay settings are pointing to the MAAS server.

3. **Verify VLAN configuration in MAAS:**
   - Add the subnet with the hosts to MAAS and create a VLAN for it.
   - Ensure that the VLAN is added to `fabric-0` and that MAAS is configured to relay through the untagged VLAN.

4. **Understand MAAS discovery process:**
   - MAAS uses PXE boot and DHCP to discover new machines. Ensure that the machines are set to network boot (PXE) and that they are on the correct subnet where MAAS can communicate with them.
   - MAAS will recognize a machine if it sees the PXE request and responds with the necessary boot files.

5. **Check for discovered hosts:**
   - Go to the "Machines" tab in the MAAS UI and check the "Discovered hosts" section to see if the new machine appears there.

6. **Troubleshoot network connectivity:**
   - Ensure there are no network issues or misconfigurations that might prevent the DHCP response from reaching MAAS. Check for VLAN tagging issues or routing problems.

7. **Review logs and configuration files:**
   - Check the [MAAS log files](/t/how-to-use-maas-systemd-logs/8103/) for any errors or warnings that might indicate issues with DHCP or PXE boot.

8. **Documentation and guides:**
   - Refer to the [official MAAS documentation](https://maas.io/docs/about-dhcp-in-maas) for detailed information on how MAAS works with DHCP and how to properly configure and troubleshoot it.

**Example command for checking DHCP leases:**
   - View the `dhcpd.leases` file to ensure that leases are being given out:
     ```sh
     cat /var/lib/dhcp/dhcpd.leases
     ```

**Next steps:**
   - If the machine is still not discovered, consider manually adding the machine to MAAS as a last resort by following the [MAAS guide on adding machines manually](https://maas.io/docs/add-machines-manually).

By following these steps, you should be able to diagnose and resolve the issue with MAAS not recognizing the used IP addresses and new machines in the subnet.

## Networking a Dell server in MAAS

**Problem:**
You have successfully set up a Dell server using MAAS, but network interfaces are not being recognized correctly in the MAAS UI, particularly when trying to create a bond interface (port channel). The second network interface (eno2) is UP and recognized by the operating system but is not shown as connected in the MAAS UI.

**Solution:**

1. **Check hardware compatibility:**
   - Ensure that both eno1 and eno2 are physically connected and recognized by the server hardware. Check for any hardware-related issues or driver compatibility problems that might be causing one of the interfaces not to be detected.

2. **Verify driver and firmware:**
   - Make sure that you have the correct network drivers installed and that the firmware for both network interfaces (eno1 and eno2) is up to date. Outdated firmware or missing drivers can cause issues with interface detection.

3. **Check network configuration:**
   - Verify that the network cables and configurations for eno1 and eno2 are correct. Ensure they are both configured to operate in the same network and subnet.

4. **MAAS UI configuration:**
   - In the MAAS UI, go to the “Machines” tab and select your server.
   - Click on the “Interfaces” section to view the detected interfaces.
   - If only one interface (eno1) is shown as UP, it may indicate that the other interface (eno2) is not being detected correctly.

5. **Troubleshoot interface detection:**
   - On the server, try running the following command to manually bring up the eno2 interface and see if it gets detected by MAAS:
     ```sh
     sudo ip link set eno2 up
     ```
   - After running the command, check the MAAS UI again to see if the second interface is now recognized.

6. **Check MAAS version:**
   - Ensure that you are using an up-to-date version of MAAS. Sometimes, issues related to hardware detection and interface recognition are resolved in newer MAAS releases.

7. **Validate networking configuration in MAAS:**
   - Use the "Validate networking configuration" button in the MAAS UI to check for any network issues.

8. **Commissioning script output:**
   - Run a commissioning script to gather detailed logs and output. This can help identify any issues with the network interfaces. Share the commissioning output with the support team or relevant forums for further analysis.

9. **Check physical connections:**
   - Ensure that there are no physical disconnects or missing wires. Sometimes, issues can be caused by simple hardware problems like loose cables.

**Example command for commissioning script:**
   - To run a commissioning script, follow the steps in the MAAS UI to commission the machine. During commissioning, MAAS will run various scripts to validate the hardware configuration. The output of these scripts can be found in the logs section of the MAAS UI.

**Follow-up actions:**
- If the BMC (Baseboard Management Controller) of the server is powered off, manually power it up and check if the network interfaces are detected correctly.
- If the issue persists after all troubleshooting steps, consider reaching out to the MAAS support team or community forums for further assistance.

By methodically verifying and comparing configurations, you should be able to pinpoint the cause of the interface detection issue and resolve the networking problem in MAAS.

## MAAS DHCP says there are no leases

**Problem:**
You are experiencing an issue where MAAS is not responding to DHCP requests from the iDRAC of a Dell server. The iDRAC's IP address is 0.0.0.0, and DHCP requests sent to MAAS do not receive replies. The DHCP logs indicate that DHCP DISCOVER messages are received on VLAN 5004, which is outside the valid VLAN range. Additionally, replacing one switch with another resolves the issue, suggesting a potential switch configuration problem.

**Solution:**

1. **Verify VLAN configuration:**
   - Ensure that the VLAN configuration on both switches (SWITCH1 and SWITCH2) is consistent and correct. Verify that the port connected to the server is configured to handle the appropriate VLANs.

2. **Check switch logs and settings:**
   - Look into the logs and settings of SWITCH1 to see if there are any discrepancies or errors that might cause the DHCP requests to be tagged incorrectly. Ensure that the VLAN settings are not misconfigured.

3. **MAAS network configuration:**
   - Double-check the network configuration in MAAS to ensure that the VLANs are correctly defined and that there are available IP addresses in the DHCP range. You can do this by navigating to the network settings in the MAAS UI.

4. **Reset iDRAC network settings:**
   - If possible, reset the network settings of the iDRAC to ensure it is sending DHCP requests correctly. Verify that the iDRAC is set to obtain an IP address via DHCP.

5. **Inspect DHCP logs:**
   - Continue monitoring the DHCP logs (`/var/log/syslog`) on the MAAS server for any further insights or repeating patterns. Check if the MAC address of the iDRAC is consistently seen in the logs.

6. **Test with a different VLAN:**
   - If feasible, temporarily configure the iDRAC to use a different VLAN to see if the issue persists. This can help isolate whether the problem is VLAN-specific.

7. **Switch configuration comparison:**
   - Since SWITCH2 works fine, compare the configuration of SWITCH1 and SWITCH2. Look for differences in how they handle VLANs, DHCP relay, and port settings.

8. **Firmware updates:**
   - Ensure that both switches and the iDRAC firmware are up-to-date. Firmware bugs can sometimes cause unexpected behavior.

**Example commands for switch troubleshooting:**
- To display VLAN configuration on a Cisco switch:
  ```sh
  show vlan brief
  ```

- To display interface configuration:
  ```sh
  show running-config interface <interface-id>
  ```

**Follow-up actions:**
- If you identify a misconfiguration on SWITCH1, correct it and test the DHCP process again.
- If the issue persists after all troubleshooting steps, consider isolating the network further or engaging with the switch vendor's support for deeper diagnostics. 

By methodically verifying and comparing configurations, you should be able to pinpoint the cause of the VLAN misidentification and resolve the DHCP leasing issue.

## Issues with PXE booting from controller with two networks

**Problem:**
You are running a MAAS 3.3 server from an LXD container with two interfaces, each on a different VLAN. PXE booting from "network 2" results in the server only getting an IP and timing out on the TFTP request for `bootx64.efi`. The issue does not occur on "network 1". A temporary workaround involved moving the subnet to a separate fabric and recommissioning/deploying, but the subnet eventually reverts to the original fabric, causing the problem to recur.

**Solution:**

1. **Verify DHCP server:**
   - Ensure there are no other DHCP servers running on "network 2" that could be conflicting with MAAS. Use tools like `dhcpdump` or `tcpdump` to detect any rogue DHCP servers.

2. **Check network switch configuration:**
   - Confirm that the switch ports are correctly configured for the VLANs. Verify that the switch is not blocking or misrouting TFTP packets.

3. **Netplan configuration:**
   - Verify the netplan configuration in your LXD container is correctly set up and applied. Here is your current configuration:

    ```yaml
    network:
      version: 2
      ethernets:
        eth0:
          addresses:
          - 10.25.51.3/23
          dhcp4: false
          nameservers:
            addresses:
            - 10.25.52.2
            - 10.25.51.3
          routes:
          - to: default
            via: 10.25.50.1
        eth1:
          addresses:
          - 10.25.54.100/24
          dhcp4: false
          nameservers:
            addresses:
            - 10.25.51.3
            - 10.25.52.2
    ```

4. **Ensure proper netplan application:**
   - Make sure the netplan configuration is applied correctly by running `sudo netplan apply` inside the MAAS container.

5. **Inspect TFTP service:**
   - Verify that the TFTP service is running and properly configured to serve files on both networks. Check for any errors in the TFTP server logs.

6. **Check MAAS logs:**
   - Look into the [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/) for any errors or warnings related to network or DHCP services.

If the issue persists after following these steps, it might be beneficial to work closely with your network team to identify any potential network-level misconfigurations or conflicts. Additionally, you may want to check for any recent changes or updates that could have affected the network or MAAS configuration.

## Get a complete list of DNS resources from the MAAS API

To get a complete list of DNS resources from the MAAS API using Python, you need to include the `all=True` parameter in your request URL. Here is a working example using the `requests` library:

```python
import json
from requests import Request, Session
from requests_oauthlib import OAuth1

# Replace with your actual keys and URL
consumer_key = 'xxxxxxxxxx'
token_key = 'yyyyyyyyyyy'
token_secret = 'zzzzzzzzzz'
base_url = 'https://my-maas-instance.com/MAAS/api/2.0/dnsresources/'

# Authentication
auth = OAuth1(consumer_key, '', token_key, token_secret)

# Headers
headers = {'Accept': 'application/json'}

# Full URL with all=True parameter
url = f'{base_url}?all=True'

# Create a session and send the request
session = Session()
request = Request('GET', url, headers=headers, auth=auth)
prepped = request.prepare()
response = session.send(prepped)

# Print the response
print(response.text)
```

In this script, make sure to replace the placeholder values (`xxxxxxxxxx`, `yyyyyyyyyyy`, `zzzzzzzzzz`, and `https://my-maas-instance.com/MAAS/api/2.0/dnsresources/`) with your actual consumer key, token key, token secret, and the MAAS instance URL, respectively.

This will retrieve the full list of DNS resources from the MAAS API, including all entries when `all=True` is used.

## Addressing SNMP errors in MAAS

### Error description:
Encountering SNMP errors when attempting to query a device’s BMC. The errors include ‘Cannot find module’ for various MIBs and ‘Timeout’ when communicating with the target IP address.

### Steps to resolve:

1. **Check SNMP Configuration:**
   Ensure SNMP is correctly configured on the BMC device. Verify the community string, SNMP version, and access control settings.

2. **Install missing MIBs:**
   - Install the required MIBs on the MAAS server. Missing MIBs often cause 'Cannot find module' errors.
   - Update the SNMP MIB repository:
     ```bash
     sudo apt-get install snmp-mibs-downloader
     sudo download-mibs
     ```

3. **Verify network connectivity:**
   - Ensure the MAAS server can reach the BMC device. Check the network connectivity and firewall rules.
   - Use `ping` or `telnet` to verify:
     ```bash
     ping <BMC_IP>
     telnet <BMC_IP> 161
     ```

4. **Test SNMP communication:**
   - Use the `snmpwalk` command to test SNMP communication manually:
     ```bash
     snmpwalk -v 2c -c <community_string> <BMC_IP>
     ```
   - Check for timeout errors or specific MIB module errors.

5. **Update MAAS and dependencies:**
   - Ensure you are using the latest version of MAAS and its dependencies. Update the system packages:
     ```bash
     sudo apt-get update
     sudo apt-get upgrade
     sudo snap refresh maas
     ```

6. **Configure SNMP on MAAS:**
   - Edit the MAAS configuration to include the correct SNMP settings. Typically, this is done in the `/etc/maas/maas.cfg` file or through the MAAS web interface.

7. **Check SNMP logs:**
   - Review the SNMP logs for detailed error messages:
   
     ```bash
     sudo journalctl -u maas
     ```

8. **Restart services:**
   - Restart the MAAS and SNMP services to apply the changes:
     ```bash
     sudo systemctl restart maas-regiond
     sudo systemctl restart maas-rackd
     ```

9. **SNMP timeout troubleshooting:**
   - If timeouts persist, increase the SNMP timeout value and retry:
     ```bash
     snmpwalk -v 2c -c <community_string> -t 60 <BMC_IP>
     ```

10. **Community support:**
    - If issues persist, consider reaching out to the community or consulting MAAS documentation and forums for specific guidance related to your hardware and MAAS version.

By following these steps, you should be able to resolve the SNMP errors and successfully query your device’s BMC using MAAS.

## Disabling BIND (named) on IPv6 in MAAS

**Scenario:**
You need to disable BIND (named) from listening on IPv6 addresses in a MAAS setup. The solution involves editing the BIND configuration to disable IPv6.

**For Snap installation:**
Snap installations of MAAS do not allow direct editing of the named configuration files because they are contained within the snap. However, you can manage named options indirectly.

**For Apt Installation:**
If MAAS is installed using apt, you can directly edit the BIND configuration files.

### Steps for Apt-installed MAAS

1. **Open the named configuration options file:**

   ```bash
   sudo nano /etc/bind/named.conf.options
   ```

2. **Edit the file to disable IPv6:**
   Find the line that specifies the IPv6 listening options and change it to disable IPv6. The line typically looks like:

   ```bash
   listen-on-v6 { any; };
   ```

   Change it to:

   ```bash
   listen-on-v6 { none; };
   ```

3. **Save and exit the file:**

   - Press `Ctrl+O` to write the changes.
   - Press `Enter` to confirm.
   - Press `Ctrl+X` to exit the editor.

4. **Restart BIND to apply the changes:**

   ```bash
   sudo systemctl restart bind9
   ```

### Verification

1. **Check the BIND status:**

   ```bash
   sudo systemctl status bind9
   ```

   Ensure there are no errors.

2. **Verify that BIND is not listening on IPv6:**

   ```bash
   sudo netstat -plnt | grep named
   ```

   This should show that named is not listening on any IPv6 addresses.

### Notes

- **MAAS Snap installation:**
  For the snap version of MAAS, this process is not directly applicable as snaps are isolated and do not allow direct modification of their internal configuration files. In such cases, consult the snap documentation or consider using an apt-based installation if you need more flexibility in configuration.

By following these steps, you should be able to disable BIND from listening on IPv6 in a MAAS environment installed via apt.

## Creating and managing DNS SRV records in MAAS

**Problem:**
Difficulty in creating and resolving DNS SRV records in MAAS, where records added via the MAAS GUI do not resolve correctly despite appearing in the zone file.

**Solution:**
Ensure that DNS SRV records are created correctly and troubleshoot potential issues with the web GUI by verifying the records directly in the zone file and ensuring that named.conf is properly updated.

**Steps to Resolve:**

1. **Verify SRV record creation via MAAS GUI:**

   - Log in to the MAAS web interface.
   - Navigate to the DNS settings and add the desired SRV records.
   - Ensure the format is correct:
     ```
     _service._protocol.name. TTL class SRV priority weight port target.
     ```
   - Example:
     ```
     _myservice._tcp.test. 30 IN SRV 10 10 1234 t1.test.
     ```

2. **Check zone file directly:**

   - Access the MAAS server and check the DNS zone file for the domain.
   - Verify that the SRV record appears correctly in the zone file.
     ```bash
     cat /var/lib/bind/maas/zone.test
     ```
   - Example:
     ```bash
     ; Zone file modified: 2023-12-09 16:00:59.338123.
     $TTL 30
     @ IN SOA test. nobody.example.com. (
     0000000951 ; serial
     600 ; Refresh
     1800 ; Retry
     604800 ; Expire
     30 ; NXTTL
     )
     @ 30 IN NS maas.
     t2 30 IN A 192.168.1.2
     t3 30 IN A 192.168.1.3
     t1 30 IN A 192.168.1.1
     _myservice._tcp 30 IN SRV 10 10 1234 t1.test.
     ```

3. **Test SRV record resolution:**

   - Use the `dig` command to query the SRV record and check the response.
     ```bash
     dig @localhost SRV _myservice._tcp.test
     ```
   - Expected output:
     ```bash
     ; <<>> DiG 9.18.18-0ubuntu0.22.04.1-Ubuntu <<>> @localhost SRV _myservice._tcp.test
     ; (1 server found)
     ;; global options: +cmd
     ;; Got answer:
     ;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 10147
     ;; flags: qr aa rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1
     
     ;; QUESTION SECTION:
     ;_myservice._tcp.test. IN SRV
     
     ;; ANSWER SECTION:
     _myservice._tcp.test. 30 IN SRV 10 10 1234 t1.test.
     
     ;; Query time: 0 msec
     ;; SERVER: 127.0.0.1#53(localhost) (UDP)
     ;; WHEN: Sat Dec 09 16:05:35 UTC 2023
     ;; MSG SIZE rcvd: 135
     ```

4. **Troubleshoot GUI issues:**

   - If records do not appear or resolve correctly, manually edit the zone file and named configuration.
   - Ensure there are no stale or incorrectly formatted entries.
   - Restart the DNS service to apply changes:
     ```bash
     sudo systemctl restart bind9
     ```

5. **Check named configuration:**

   - Ensure that the named configuration includes the correct zone settings and paths to the zone files.
     ```bash
     cat /etc/bind/named.conf
     ```

**Example:**

1. **Create SRV record in MAAS GUI:**
   - Navigate to the domain `test` and add the SRV record `_myservice._tcp.test`.

2. **Verify zone file:**
   - Confirm the zone file has the correct entries.
     ```bash
     cat /var/lib/bind/maas/zone.test
     ```

3. **Test resolution:**
   - Use `dig` to test the SRV record.
     ```bash
     dig @localhost SRV _myservice._tcp.test
     ```

4. **Manual edit and restart (if needed):**
   - Edit zone file if the GUI fails and restart DNS service.
     ```bash
     sudo nano /var/lib/bind/maas/zone.test
     sudo systemctl restart bind9
     ```

By following these steps, you can create and manage DNS SRV records in MAAS, ensuring they are correctly configured and resolvable.

## Legacy BIOS boot from second NIC

**Problem:**
When using MAAS with machines that boot via legacy BIOS, there's an issue where PXE booting from the second NIC results in a "No boot filename received" error. This occurs despite the machine receiving a DHCP offer.

**Solution:**
The issue is likely due to the limitation that, until MAAS version 3.5, booting from the first NIC is required for machines using legacy BIOS. To resolve this, you need to configure the machines to boot from the first NIC and use the second NIC for other network configurations.

**Steps to resolve:**

1. **Verify boot order:**
   - Ensure that the boot order in the BIOS settings of your machines prioritizes the first NIC for PXE booting.

2. **Reconfigure MAAS network settings:**
   - Ensure that the MAAS server and DHCP configurations are set up correctly for the first NIC.

3. **Update MAAS machine entries:**
   - If necessary, re-add the machines in MAAS using the MAC address of the first NIC.

**Detailed steps:**

**a. Check and configure BIOS settings:**

1. **Access BIOS/UEFI settings:**
   - Restart the machine and enter the BIOS/UEFI setup (usually by pressing F2, F10, F12, or Delete during boot).
   
2. **Set boot order:**
   - Navigate to the boot settings and set the first NIC as the primary boot device for PXE booting.

**b. Update MAAS configuration:**

1. **Re-add machine with first NIC:**
   - In the MAAS UI, ensure the machine is enlisted with the MAC address of the first NIC.
   
   **Example command to add machine with first NIC:**
   ```bash
   maas $PROFILE machines add mac_addresses=$FIRST_NIC_MAC
   ```

2. **Verify DHCP configuration:**
   - Ensure DHCP is correctly configured for the first NIC in the subnet used for PXE booting.

**Example DHCP configuration check:**
   ```bash
   sudo nano /etc/dhcp/dhcpd.conf
   ```
   - Ensure the correct interface and subnet are specified.

**c. Re-commission the machine:**

1. **Commission the machine:**
   - Re-commission the machine in MAAS using the first NIC for PXE booting.

   **Example command to commission machine:**
   ```bash
   maas $PROFILE machine commission $MACHINE_ID
   ```

2. **Check logs for errors:**
   - Monitor the [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/) for any errors related to network configuration.

**Example workflow:**

1. **Verify boot order in BIOS:**
   - Ensure the first NIC is set as the primary boot device.

2. **Add machine to MAAS with first NIC:**
   ```bash
   maas $PROFILE machines add mac_addresses=$FIRST_NIC_MAC
   ```

3. **Configure and verify DHCP for first NIC:**
   ```bash
   sudo nano /etc/dhcp/dhcpd.conf
   ```

4. **Commission the machine:**
   ```bash
   maas $PROFILE machine commission $MACHINE_ID
   ```

5. **Monitor the [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/).

By following these steps, you can ensure that machines with legacy BIOS can successfully PXE boot from the first NIC, resolving the "No boot filename received" error and enabling proper commissioning and deployment in MAAS.

## Using routed subnets

**Problem:**
The MAAS server is set up on VLAN 1000 with subnet 10.10.10.0/24 and is configured to serve another subnet 10.20.20.0/24 via DHCP relay. Devices in the 10.20.20.0/24 subnet can receive DHCP addresses but fail to connect to the TFTP server, resulting in timeouts.

**Solution:**
To resolve this issue, you need to ensure that TFTP and other necessary services can communicate properly across subnets. This involves verifying network configurations and ensuring that MAAS is set up to handle requests from both subnets.

**Steps to resolve the issue:**

1. **Check the [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/)** to verify that the TFTP requests are being received and to identify any potential issues.

2. **Verify network configuration:**
   - Ensure that network devices are correctly configured to route traffic between the subnets. This includes ensuring that the DHCP relay is functioning properly and that there are no routing issues.

   **Example configuration check:**
   - Verify that routers or switches between the VLANs are configured to allow TFTP traffic.

3. **Enable ProxyDHCP:**
   - Ensure that ProxyDHCP is enabled on the MAAS server to handle PXE boot requests.

   **Example command to enable ProxyDHCP:**
   ```bash
   maas $PROFILE maas set-config name=enable_proxy value=true
   ```

4. **Check TFTP configuration:**
   - Verify that the TFTP server on the MAAS rack controller is properly configured to serve requests from both subnets.

   **Example TFTP configuration check:**
   ```bash
   sudo nano /etc/default/tftpd-hpa
   ```
   - Ensure the TFTP server is listening on the correct interfaces.

5. **Ensure IP forwarding:**
   - Verify that IP forwarding is enabled on the MAAS server to allow routing between the subnets.

   **Example command to enable IP forwarding:**
   ```bash
   sudo sysctl -w net.ipv4.ip_forward=1
   ```

6. **Firewall configuration:**
   - Double-check that there are no firewall rules blocking traffic between the subnets.

   **Example firewall check:**
   ```bash
   sudo ufw status
   ```

7. **Network device configuration:**
   - Ensure that network devices (routers/switches) are configured to forward TFTP and HTTP requests from devices in the 10.20.20.0/24 subnet to the MAAS server in the 10.10.10.0/24 subnet.

   **Example network configuration:**
   ```text
   Router Configuration:
   - DHCP relay pointing to 10.10.10.2
   - IP routes allowing traffic between 10.20.20.0/24 and 10.10.10.0/24
   ```

**Example workflow:**

1. **Check the [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/):**

2. **Verify network devices configuration:**
   - Ensure that all routers and switches are correctly configured to allow TFTP traffic.

3. **Enable ProxyDHCP on MAAS:**
   ```bash
   maas $PROFILE maas set-config name=enable_proxy value=true
   ```

4. **Check TFTP server configuration:**
   ```bash
   sudo nano /etc/default/tftpd-hpa
   ```
   - Ensure it listens on the correct interfaces.

5. **Enable IP forwarding:**
   ```bash
   sudo sysctl -w net.ipv4.ip_forward=1
   ```

6. **Check firewall status:**
   ```bash
   sudo ufw status
   ```

By following these steps, you can troubleshoot and resolve the issue of the MAAS server not responding to TFTP requests from the 10.20.20.0/24 subnet, ensuring that all devices can properly communicate with the MAAS server across different subnets.

## Commissioning failed due to lldpd

**Problem:**
The commissioning process fails at the "lldpd" installation step due to the error "Unable to locate package lldpd." This issue occurs in a disconnected environment where a local mirror of the Ubuntu repository is used.

**Solution:**
The issue is likely due to missing repository components in the local mirror configuration, particularly the "universe" component where the `lldpd` package resides.

**Steps to resolve:**

1. **Check repository components:**
   - Ensure that the local mirror includes the necessary repository components (`main`, `universe`, `restricted`, and `multiverse`).

2. **Update MAAS settings:**
   - Update the MAAS settings to ensure it uses the local mirror correctly, including all required components.

3. **Verify and update preseed configuration:**
   - Verify the preseed configuration to ensure it includes all necessary components.

4. **Detailed steps:**

   **a. Verify local mirror configuration:**
   - Ensure your local mirror configuration includes the `universe` component. 

   **Example local mirror configuration:**
   ```bash
   deb http://192.168.1.100/repos/archive.ubuntu.com/ubuntu focal main universe restricted multiverse
   ```

   **b. Update MAAS proxy settings:**
   - Ensure MAAS is configured to use the local mirror as a proxy and includes all components.

   **Example MAAS proxy configuration:**
   ```bash
   sudo maas $PROFILE maas set-config name=http_proxy value="http://192.168.1.100:8000/"
   ```

   **c. Verify preseed configuration:**
   - Access the preseed configuration to ensure it includes all necessary repository components.

   **Example command to access preseed:**
   ```bash
   http://<maas_ip>:5240/MAAS/metadata/latest/by-id/<system_id>/?op=get_preseed
   ```

   **Example preseed configuration:**
   ```yaml
   sources:
     repo_infra_3:
       source: deb http://192.168.1.100/repos/archive.ubuntu.com/ubuntu $RELEASE main universe restricted multiverse
   ```

   **d. Disable official repositories:**
   - Since the environment is disconnected from the internet, disable the official repositories to avoid errors.

   **Example configuration to disable official repositories:**
   ```yaml
   sources:
     repo_infra_3:
       source: deb http://192.168.1.100/repos/archive.ubuntu.com/ubuntu $RELEASE main universe restricted multiverse
   ```

   **e. Re-run commissioning:**
   - Re-run the commissioning process to ensure the changes take effect.

5. **Verify package availability:**
   - Confirm that the `lldpd` package is available in the local mirror by running the following command on a test machine:
   ```bash
   sudo apt-get update
   sudo apt-get install lldpd
   ```

By following these steps, you can ensure that the necessary repository components are included and configured correctly, allowing the commissioning process to complete successfully without errors related to the `lldpd` package.

## Adding domains to the DNS search list

**Problem:**
You want to add two additional domains to the DNS search list for a subnet in MAAS, but there doesn't seem to be an option to set this directly in the UI or through typical configuration methods.

**Solution:**
To add additional domains to the DNS search list for a subnet in MAAS, you can use a custom cloud-init script to configure the `resolv.conf` file. Follow these steps:

1. **Use cloud-init configuration:**
   - Cloud-init can be used to configure the DNS search list by specifying the appropriate settings in a custom cloud-init script.

2. **Steps to configure DNS search list:**

   **a. Create a custom cloud-init script:**
   - Create a cloud-init script that adds the desired search domains to the `resolv.conf` file.

   **Example cloud-init script:**
   ```yaml
   #cloud-config
   write_files:
     - path: /etc/cloud/cloud.cfg.d/99-custom-dns.cfg
       content: |
         network:
           config: disabled
   runcmd:
     - echo "search domain1.com domain2.com" >> /etc/resolv.conf
     - netplan apply
   ```

   **b. Update MAAS machine configuration:**
   - Apply this cloud-init script to the machines managed by MAAS. You can do this by adding the script to the custom commissioning and deployment scripts in the MAAS UI or via the CLI.

   **Example command to apply custom cloud-init script:**
   ```bash
   maas $PROFILE machine update $MACHINE_ID user_data="$(base64 -w 0 /path/to/your/cloud-init.yaml)"
   ```

   **c. Verify DNS configuration:**
   - After the machines have been deployed, verify that the `resolv.conf` file has the correct DNS search list entries.

   **Example command to check `resolv.conf`:**
   ```bash
   cat /etc/resolv.conf
   ```

3. **Ensure persistence:**
   - Since cloud-init might overwrite the network configuration on reboot, ensure that your custom cloud-init script disables network configuration management by cloud-init.

   **Example configuration to disable network configuration by cloud-init:**
   ```yaml
   network:
     config: disabled
   ```

   - Add this configuration to your cloud-init script to prevent cloud-init from overwriting your custom DNS settings.

**Example workflow:**

1. **Create custom cloud-init script:**
   ```yaml
   #cloud-config
   write_files:
     - path: /etc/cloud/cloud.cfg.d/99-custom-dns.cfg
       content: |
         network:
           config: disabled
   runcmd:
     - echo "search domain1.com domain2.com" >> /etc/resolv.conf
     - netplan apply
   ```

2. **Apply script to MAAS machine:**
   ```bash
   maas $PROFILE machine update $MACHINE_ID user_data="$(base64 -w 0 /path/to/your/cloud-init.yaml)"
   ```

3. **Deploy and verify:**
   - Deploy the machine and verify the DNS configuration.
   ```bash
   cat /etc/resolv.conf
   ```

By following these steps, you can add additional domains to the DNS search list for your MAAS-managed subnets, ensuring proper DNS resolution for your deployed machines.

## Clients get the image but don’t appear on the GUI

**Problem:**
Clients (VMs) receive the image and boot correctly from MAAS, but they do not appear in the MAAS GUI under the Machines section.

**Solution:**
This issue could be due to network misconfiguration or incorrect settings in MAAS that prevent the clients from being properly enlisted and commissioned. Follow these steps to resolve the issue:

1. **Verify network configuration:**
   - Ensure that DHCP is enabled on the correct VLAN where your VMs are located.
   - Check that the DHCP server sends the DHCP offer with the MAAS IP provided in the "next server" property.

2. **Check MAAS logs:**
   - Review [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/) for any errors or warnings that might indicate why the clients are not appearing in the GUI.

3. **Ensure proper enlistment:**
   - Confirm that the clients are properly enlisting with MAAS. This includes ensuring that the correct commissioning scripts are running.

4. **Steps to resolve the issue:**

   **a. Verify DHCP configuration:**
   - Ensure that the DHCP server on MAAS is correctly configured to provide IP addresses to the VMs on the correct VLAN.

   **Example command to check DHCP configuration:**
   ```bash
   maas $PROFILE dhcps read
   ```

   **b. Check MAAS logs:**
   - Check the [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/) for any errors or issues related to DHCP or network configuration.

   **c. Verify network interface configuration:**
   - Ensure that the network interfaces on the MAAS VM are correctly configured and match the settings in MAAS.

   **d. Ensure correct enlistment:**
   - Verify that the VMs are set up to enlist correctly with MAAS. This includes making sure they are using the correct PXE boot settings.

   **Example steps to verify PXE boot:**
   1. Ensure the VM is set to network boot (PXE).
   2. Verify that the correct boot image is being used.

   **e. Check commissioning status:**
   - Make sure the VMs are commissioning correctly and check their status in MAAS.

   **Example command to check commissioning status:**
   ```bash
   maas $PROFILE machines read
   ```

5. **Additional configuration:**
   - Ensure that the MAAS server and clients are on the same network and that there are no firewall rules blocking communication.

**Example workflow:**

1. **Check DHCP and network configuration:**
   ```bash
   maas $PROFILE dhcps read
   ```

2. **Check the [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/)**.

3. **Verify PXE boot settings:**
   - Ensure VMs are set to boot from the network (PXE).

4. **Check commissioning status:**
   ```bash
   maas $PROFILE machines read
   ```

By following these steps, you can diagnose and resolve the issue of clients receiving images but not appearing in the MAAS GUI. This approach ensures proper network configuration and correct commissioning of the VMs.

## HA DHCP for relayed subnets

**Problem:**
Implementing high availability (HA) for DHCP in relayed subnets using MAAS is not straightforward, and the standard architecture restricts adding a secondary rack controller in these scenarios.

**Solution:**
To achieve HA for DHCP services in relayed subnets with MAAS, follow these steps:

1. **Understand MAAS DHCP configuration:**
   - MAAS typically allows for setting a primary and secondary rack controller for DHCP services directly connected to subnets. For relayed DHCP, both rack controllers must be aware of each other and be able to manage the DHCP relay for the target subnets.

2. **Update VLAN configuration via CLI:**
   - Use the MAAS CLI to configure the primary and secondary rack controllers for DHCP. Ensure both rack controllers are on the same VLAN where they can communicate effectively.

3. **Steps for Configuration:**

   **a. Identify VLAN and fabric IDs:**
   - Determine the fabric ID and VLAN ID for the subnets where DHCP needs to be relayed.

   **b. Configure primary and secondary rack controllers:**
   - Update the VLAN configuration to set the primary and secondary rack controllers.

   **Example commands:**
   ```bash
   maas $PROFILE vlan update $FABRIC_ID $VLAN_TAG dhcp_on=True \
       primary_rack=$PRIMARY_RACK_CONTROLLER \
       secondary_rack=$SECONDARY_RACK_CONTROLLER 
   ```

   **c. Configure DHCP relay:**
   - Use the CLI to set up the DHCP relay, ensuring both rack controllers can handle the relayed DHCP traffic.

   **Example command:**
   ```bash
   maas $PROFILE vlan update $FABRIC_ID $VLAN_ID_SRC relay_vlan=$VLAN_ID_TARGET
   ```

4. **Network considerations:**
   - Ensure that both rack controllers are connected to the same network infrastructure that supports VLANs and DHCP relay. They should be able to communicate over the same VLAN.

5. **HA setup with IP helpers:**
   - Configure IP helpers on your network switches to relay DHCP requests to both the primary and secondary rack controllers. This will ensure that if one rack controller goes down, the other can still handle DHCP requests.

6. **Verify configuration:**
   - After configuration, verify that both rack controllers are operational and can handle DHCP requests. Check the MAAS UI and logs to confirm there are no errors.

**Example workflow:**

1. **Get fabric and VLAN IDs:**
   ```bash
   maas $PROFILE fabrics read
   maas $PROFILE vlans read $FABRIC_ID
   ```

2. **Update VLAN for DHCP and relay:**
   ```bash
   maas $PROFILE vlan update $FABRIC_ID $VLAN_TAG dhcp_on=True \
       primary_rack=$PRIMARY_RACK_CONTROLLER \
       secondary_rack=$SECONDARY_RACK_CONTROLLER 

   maas $PROFILE vlan update $FABRIC_ID $VLAN_ID_SRC relay_vlan=$VLAN_ID_TARGET
   ```

3. **Configure IP helpers on network switch:**
   - Set IP helpers to point to both rack controllers' IP addresses on the network switch.

By following these steps, you can set up HA for DHCP in relayed subnets using MAAS, ensuring redundancy and high availability for your network configuration. This approach leverages both the MAAS CLI for detailed configuration and network infrastructure for effective DHCP relay.

## External DHCP configuration

**Problem:**
MAAS passes the commissioning and deployment stages but gets stuck in the "rebooting" stage with an `errno 101 network is unreachable` error. This issue may be related to the external DHCP configuration.

**Solution:**
To resolve issues related to external DHCP configuration in MAAS, follow these steps:

1. **Verify external DHCP server:**
   - Ensure that the external DHCP server is properly configured and operational on the subnet where the MAAS rack controller is connected.

2. **Enable network discovery:**
   - Make sure that network discovery is enabled in MAAS and that the rack controller is checking for external DHCP servers regularly.

3. **Check logs:**
   - Inspect the [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/) to verify that the rack controller is detecting the external DHCP server.

4. **Set static IP configuration:**
   - If using a virtual environment like OpenVSwitch, configure the server’s network settings to static IP addresses to avoid issues during boot.

5. **Detailed steps:**

   **a. Verify external DHCP server:**
   - Ensure that the external DHCP server is providing IP addresses correctly. Check if the external DHCP server's host is visible in the network discovery results.

   **b. Enable network discovery:**
   - Confirm that network discovery is enabled and set to check every 10 minutes.

   **Example:**
   ```bash
   maas admin subnet update <subnet-id> manage_discovery=true
   ```

   **c. Check logs:**
   - Review the [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/) to ensure the external DHCP server is being detected.

   **d. Set static IP configuration:**
   - If the issue persists, configure the server's network settings to use a static IP address. This is particularly useful for virtual environments where DHCP might not function as expected.

   **Example netplan configuration (static IP):**
   ```yaml
   network:
     ethernets:
       ens16:
         addresses:
           - 192.168.30.20/23
         nameservers:
           addresses:
             - 192.168.30.1
             - 192.168.30.2
         routes:
           - to: default
             via: 192.168.30.10
     version: 2
   ```

   **Apply the changes:**
   ```bash
   sudo netplan apply
   ```

6. **Additional configuration:**
   - Ensure that the network interfaces and routing are correctly set up to allow communication with the MAAS server.

By following these steps, users can resolve the `errno 101 network is unreachable` error and ensure that the MAAS deployment process completes successfully. This approach addresses both DHCP configuration issues and network interface settings.

## Errno 101 - network is unreachable

**Problem:**
MAAS passes the commissioning and deployment stages but gets stuck in the "rebooting" stage with an `errno 101 network is unreachable` error. This occurs even with a standard installation without using a cloud-init script.

**Solution:**
This issue can often be related to external DHCP configuration or network misconfiguration. Here are steps to resolve the issue:

1. **Verify network configuration:**
   - Ensure that the network interfaces are correctly configured and can reach the MAAS metadata service.

2. **Check DHCP settings:**
   - Verify that DHCP is correctly set up and that the deployed machine receives the correct IP address and can communicate with the MAAS server.

3. **Modify cloud-init configuration:**
   - Ensure that the cloud-init configuration is correctly set up to avoid network-related issues during the rebooting stage.

4. **Detailed steps:**

   **a. Verify network interfaces:**
   - Check the network configuration on the deployed machine to ensure it has the correct IP settings and can reach the MAAS server.

   **Example commands:**
   ```bash
   ip addr show
   ip route show
   ```

   **b. Check DHCP and DNS configuration:**
   - Ensure that the DHCP server provides the correct IP address, subnet mask, gateway, and DNS settings to the deployed machine.

   **Example:**
   - Ensure that the machine receives an IP address in the correct subnet and can reach the MAAS server.

   **c. Modify cloud-init configuration:**
   - Modify the cloud-init configuration to disable attempts to contact the MAAS metadata server if it is not reachable.

   **Example cloud-init script:**
   ```bash
   #!/bin/bash
   # disable cloud-init network configuration after deployment
   sudo touch /etc/cloud/cloud-init.disabled
   ```

   **d. Update network configuration:**
   - Update the network configuration files on the deployed machine to ensure it uses the correct network settings.

   **Example netplan configuration:**
   ```yaml
   network:
     version: 2
     ethernets:
       enp1s0:
         dhcp4: true
         nameservers:
           addresses:
             - 8.8.8.8
             - 8.8.4.4
   ```

   **Apply the changes:**
   ```bash
   sudo netplan apply
   ```

5. **Check external DHCP configuration:**
   - If using an external DHCP server, ensure it is correctly configured to work with MAAS.

By following these steps, you can resolve the `errno 101 network is unreachable` error during the rebooting stage in MAAS, ensuring that the deployed machine can correctly communicate with the MAAS server and complete the deployment process.

## Post-deployment network issues

**Problem:**
Users face issues when switching the network interface of a deployed VM from an isolated deployment network to a bridged network, causing the VM to hang or freeze during boot.

**Solution:**
MAAS does not support reassigning a deployed machine to a new subnet directly. To address this, follow these steps:

1. **Avoid switching networks:**
   - To avoid issues, do not switch the VM's network interface after deployment. Instead, ensure that the VM is configured with the correct network settings from the start.

2. **Use a different router:**
   - If using an ISP router that does not support VLANs or advanced network settings, consider adding another router that can manage your home network effectively.

3. **Manual network configuration:**
   - If you must change the network interface, manually reconfigure the network settings on the VM after switching it to the bridged network.

4. **Detailed steps:**

   **a. Update cloud-init configuration:**
   - Ensure cloud-init does not attempt to contact the MAAS metadata server on the isolated network once the VM is moved.

   **Example script:**
   ```bash
   #!/bin/bash
   # disable cloud-init network configuration after deployment
   sudo touch /etc/cloud/cloud-init.disabled
   ```

   **b. Modify network configuration:**
   - Manually update the network configuration files on the VM to match the new network settings.

   **Example netplan configuration:**
   ```yaml
   network:
     version: 2
     ethernets:
       enp1s0:
         dhcp4: true
   ```

   **c. Apply network changes:**
   - Apply the changes to ensure the VM uses the new network configuration.

   **Example commands:**
   ```bash
   sudo netplan apply
   ```

5. **Add a custom router:**
   - Add a custom router in front of your ISP router to handle DHCP, VLANs, and other advanced network features.

   **Example setup:**
   - ISP router provides internet connectivity.
   - Custom router manages the internal network, DHCP, and VLANs.
   - Connect MAAS and VMs to the custom router.

By following these steps, users can manage network configurations more effectively and avoid issues related to switching network interfaces post-deployment. This approach ensures that VMs operate correctly within the desired network setup.

## Controller interface/network issues

**Problem:**
Users experience issues with MAAS using unintended network interfaces, particularly in multi-homed environments with Docker running on the same system. Specific challenges include unwanted interface detection, persistent subnets, and network discovery on unselected subnets.

**Solution:**
To address these issues and better manage network interfaces and subnets in MAAS, follow these steps:

1. **Bind MAAS to a single interface:**
   - While MAAS does not support binding to a single interface out of the box, you can control which interfaces MAAS services use by configuring individual components such as nginx, squid, and rsyslogd.

2. **Remove unwanted interfaces:**
   - Unfortunately, MAAS does not provide a direct way to remove interfaces through the GUI or CLI if they keep reappearing. However, you can take steps to ignore certain interfaces like `docker0`.

3. **Ignore certain interfaces:**
   - To ignore specific interfaces, you can use custom scripts or configuration files to exclude them from MAAS management.

4. **Configure network services:**
   - Customize the `named.conf` file to control DNS behavior and prevent unwanted DNS resolution on specific subnets.

5. **Detailed steps:**

   **a. Exclude Docker interface:**
   - Prevent MAAS from using the `docker0` interface by configuring the system to exclude it. Create a script to modify the network configuration.

   **Example script:**
   ```bash
   #!/bin/bash
   # Exclude docker0 interface from MAAS management
   INTERFACE="docker0"
   IP_ADDR=$(ip addr show $INTERFACE | grep "inet\b" | awk '{print $2}' | cut -d/ -f1)

   if [ -n "$IP_ADDR" ]; then
     echo "Exclude $INTERFACE ($IP_ADDR) from MAAS"
     ip link set $INTERFACE down
     ip addr flush dev $INTERFACE
   fi
   ```

   **b. Customize `named.conf`:**
   - Modify the `named.conf` file to prevent `named` from using specific subnets.

   **Example configuration:**
   ```bash
   options {
     ...
     listen-on { 127.0.0.1; <your-desired-interface-ip>; };
     ...
   };
   ```

   **c. Modify network configuration:**
   - Adjust the network configuration files to ensure MAAS services bind only to the desired interface.

   **Example for `nginx`:**
   ```bash
   server {
       listen <your-desired-interface-ip>:80;
       server_name maas.local;
       ...
   }
   ```

   **d. Disable unwanted subnet management:**
   - Use MAAS CLI to disable subnet management features on undesired subnets.

   **Example CLI commands:**
   ```bash
   maas admin subnet update <subnet-id> manage_allocation=false
   maas admin subnet update <subnet-id> manage_discovery=false
   maas admin subnet update <subnet-id> allow_dns=false
   ```

6. **Review and restart services:**
   - After making these changes, restart the MAAS services to apply the new configuration.

   **Restart MAAS services:**
   ```bash
   sudo systemctl restart maas-regiond
   sudo systemctl restart maas-rackd
   ```

By following these steps, users can better control which network interfaces and subnets are managed by MAAS, addressing issues related to unwanted interface usage and persistent subnets. This approach ensures that MAAS operates within the desired network configuration parameters.

## Adding VLAN interfaces to LXD VMs

**Problem:**
Users need to add VLAN interfaces to LXD VMs in MAAS but face limitations in modifying VMs post-creation and ensuring proper VLAN tagging.

**Solution:**
To add VLAN interfaces to LXD VMs, follow these steps:

1. **Configure VLAN interfaces on the VM host:**
   - The VM host should have VLAN interfaces configured to match the desired VLANs. This setup is done on the VM host at the OS level.

2. **Create bridges for VLAN interfaces:**
   - For each VLAN you want to expose to the VMs, create a bridge with the corresponding VLAN interface inside it. This allows the VMs to have untagged interfaces while ensuring that the traffic is tagged as it leaves the host.

3. **Step-by-step configuration:**

   **a. Add VLAN interface to MAAS rack controller:**
   - Add a VLAN interface to the MAAS rack controller and assign an IP address.
   - Restart MAAS to ensure it detects the new interface.
   - Add a subnet and VLAN in MAAS and enable DHCP on the VLAN.

   **Example:**
   ```bash
   # Add VLAN 500 to physical interface eth0
   sudo ip link add link eth0 name eth0.500 type vlan id 500
   sudo ip addr add 150.150.150.1/24 dev eth0.500
   sudo ip link set dev eth0.500 up
   ```

   **b. Create bridge interface:**
   - Create a bridge interface with the new VLAN interface as a member.
   
   **Example:**
   ```bash
   # Create bridge br500 and add eth0.500 as a member
   sudo brctl addbr br500
   sudo brctl addif br500 eth0.500
   sudo ip link set dev br500 up
   ```

   **c. Configure netplan (if using):**
   - Update the Netplan configuration to persist the VLAN and bridge setup.

   **Example:**
   ```yaml
   network:
     version: 2
     ethernets:
       eth0:
         dhcp4: true
     vlans:
       eth0.500:
         id: 500
         link: eth0
         addresses: [150.150.150.1/24]
     bridges:
       br500:
         interfaces: [eth0.500]
         dhcp4: no
   ```
   - Apply the Netplan configuration:
   ```bash
   sudo netplan apply
   ```

4. **Create VMs in MAAS:**
   - When creating VMs in MAAS, specify an interface and select the subnet corresponding to the desired VLAN. This ensures that the VMs are placed in the correct VLAN.

By following these steps, users can successfully add VLAN interfaces to LXD VMs in MAAS, ensuring proper VLAN tagging and network configuration. This setup allows VMs to operate with untagged interfaces while maintaining VLAN traffic tagging at the host level.

## Netplan configuration ignored when deploying a machine

**Problem:**
The Netplan configuration provided in the `cloud-init` script is being ignored, resulting in static IP settings instead of the desired DHCP configuration.

**Solution:**
To ensure the network configuration is correctly applied during deployment, follow these steps:

1. **Edit machine's interfaces in MAAS:**
   - Before deploying the machine, edit the machine's network interfaces in MAAS to set the IP mode to DHCP. This avoids the need for `cloud-init` to handle network configuration.

2. **Default DHCP for future machines:**
   - While it's not currently possible to make DHCP the default for all future machines in MAAS, you can include this configuration as part of your deployment automation.

3. **Custom `cloud-init` script:**
   - If you still prefer to use a `cloud-init` script, ensure it correctly sets up the network interfaces. However, due to current limitations, you may need a workaround to apply Netplan configuration.

4. **Workaround with bash script:**
   - Use a bash script within `cloud-init` to manually write the Netplan configuration and apply it. This can be done using the `runcmd` section of the `cloud-init` script.

   Example `cloud-init` script with bash workaround:
   ```yaml
   #cloud-config
   packages:
     - qemu-guest-agent
     - openssh-server

   users:
     - default
     - name: untouchedwagons
       gecos: untouchedwagons
       primary_group: untouchedwagons
       groups: sudo
       sudo: ALL=(ALL) NOPASSWD:ALL
       shell: /bin/bash
       ssh_import_id:
         - gh:UntouchedWagons

   runcmd:
     - [ systemctl, enable, --now, qemu-guest-agent ]
     - [ systemctl, enable, --now, ssh ]
     - |
       cat <<EOF > /etc/netplan/01-netcfg.yaml
       network:
         version: 2
         ethernets:
           ens18:
             match:
               macaddress: 'bc:24:11:e5:41:b7'
             dhcp4: true
             dhcp-identifier: mac
       EOF
       netplan apply
   ```

5. **Automation integration:**
   - Integrate these configurations into your existing automation framework (e.g., Ansible, Terraform) to ensure consistent and repeatable deployments.

By following these steps, you can ensure that the network configuration is applied correctly during machine deployment in MAAS, avoiding the issues with ignored Netplan settings.

## Pre-registering machine with IPMI address as FQDN

**Problem:**
Users encounter issues when trying to set the IPMI IP address field as an FQDN in MAAS. The machine gets registered with an IPv4 address associated with the FQDN, and the commissioning process does not complete.

**Solution:**
To address this issue and implement workarounds, follow these steps:

1. **Direct FQDN usage:**
   - Currently, MAAS does not support using FQDN directly for the `power_address` field. The `power_address` must be an IPv4 or IPv6 address as per the BMC enlistment documentation.

2. **Workarounds:**

   **a. Use Unique hostnames in the cluster:**
   - Ensure each machine in the cluster has a unique hostname. This can help in distinguishing and managing machines more effectively.

   **b. Assign FQDN management hostnames:**
   - Assign a unique management FQDN to the BMC/IPMI IP of each machine. For example, use `[hostname]-mgmt` as the FQDN for the IPMI address.

   **c. Update BMC IP using Python script:**
   - Write a Python script that updates the BMC IP address for each machine using the MAAS API. Schedule this script to run periodically (e.g., every 5 minutes) using `cron`.

   Example Python script:
   ```python
   import maas.client
   from maas.client import login
   from maas.client.enum import NodeStatus

   MAAS_API_URL = 'http://<MAAS_SERVER>/MAAS/'
   API_KEY = '<YOUR_API_KEY>'
   FQDN_SUFFIX = '-mgmt'

   def update_bmc_ips():
       client = login(MAAS_API_URL, API_KEY)
       nodes = client.machines.list(status=NodeStatus.READY)
       for node in nodes:
           hostname = node.hostname
           fqdn = f"{hostname}{FQDN_SUFFIX}"
           ip_address = socket.gethostbyname(fqdn)
           node.power_address = ip_address
           node.save()

   if __name__ == "__main__":
       update_bmc_ips()
   ```

   - Add the script to `crontab` to run every 5 minutes:
     ```bash
     */5 * * * * /usr/bin/python3 /path/to/update_bmc_ips.py
     ```

By following these steps, users can manage their MAAS setup more effectively, even when direct FQDN usage is not supported for IPMI addresses. The provided workarounds ensure that the IPMI addresses are updated and managed correctly using the MAAS API and periodic scripts.

## Automating initial configuration settings for new machines

**Problem:**
Users need to manually configure network interfaces to DHCP and set power configurations to Manual for new machines added to MAAS, seeking a way to automate these settings.

**Solution:**
To automate the initial configuration settings for new machines in MAAS, follow these steps:

1. **Use preseed scripts:**
   - Utilize MAAS preseed scripts to automate network and power configurations. Preseed scripts can run commands during different stages of machine deployment.

2. **Curtin userdata:**
   - Modify `curtin_userdata` to include early commands for setting network interfaces to DHCP and power configuration to Manual. Add these configurations to the preseed file.

   Example preseed configuration:
   ```yaml
   early_commands:
     10_dhcp: |
       for nic in $(ls /sys/class/net/ | grep -v lo); do
         echo "dhclient ${nic}" >> /etc/network/interfaces.d/${nic};
         dhclient ${nic}
       done
     20_power: |
       echo "manual" > /etc/maas/power.conf
   ```

3. **MAAS CLI:**
   - Use the MAAS CLI to automate the setting of DHCP and power configuration for newly added machines. Create a script to be run after the machine is added to MAAS.

   Example script:
   ```bash
   #!/bin/bash
   MACHINE_ID=$1

   # Set network interface to DHCP
   maas admin interface link-subnet $MACHINE_ID \
     $(maas admin interfaces read $MACHINE_ID | jq '.[0].id') \
     mode=DHCP

   # Set power configuration to Manual
   maas admin machine update $MACHINE_ID power_type=manual
   ```

4. **Automate through hooks:**
   - Use MAAS hooks to trigger the script whenever a new machine is added. Hooks can be configured to execute scripts based on specific events.

5. **Check certified hardware:**
   - Ensure that the hardware being added to MAAS is certified and recognized by MAAS. This helps in automatic detection and configuration.

6. **Custom automation:**
   - Integrate these steps into your existing automation framework if you have one. Tools like Ansible, Terraform, or custom scripts can be used to manage these configurations.

By implementing these steps, users can automate the initial configuration settings for new machines in MAAS, reducing manual intervention and streamlining the deployment process.

## VLAN issues and rack controller configuration

**Problem:**
Users encounter issues with VLANs not being utilized on any rack controller, leading to problems with DHCP and network connectivity.

**Solution:**
To troubleshoot and resolve VLAN issues in MAAS, follow these steps:

1. **Configure VLAN interfaces:**
   - Ensure that VLAN interfaces are correctly configured on the rack controller with proper IDs, links, and IP addresses. Use `netplan` to apply configurations:
     ```bash
     sudo netplan apply
     ```

2. **Define subnets properly:**
   - Verify that subnets are defined correctly in MAAS for each VLAN. Check that the network, gateway, and DNS information are accurately entered.

3. **Physical connections:**
   - Confirm that the rack controller is physically connected to the appropriate networks and VLANs. If using a managed switch, ensure that ports are configured for the correct VLANs.

4. **Check MAAS logs:**
   - Review the [MAAS logs](/t/how-to-use-maas-systemd-logs/8103/) for any errors related to VLANs or DHCP:

5. **Force network re-detection:**
   - Remove and re-add the rack controller in MAAS to force it to re-detect available networks and VLANs.

6. **Test DHCP on single VLAN:**
   - Enable DHCP on one VLAN at a time to identify any working configurations.

7. **Static IP address:**
   - Consider setting a static IP address on the VLAN interface to avoid DHCP conflicts.

8. **Restart rack controller:**
   - Restart the rack controller to ensure it reconnects correctly to MAAS and the VLANs.

9. **Reinstall rack controller:**
   - As a last resort, reinstall the rack controller following the official documentation to resolve any networking issues:
     - Ensure the rack controller is not installed on the same machine as the region controller.

10. **DHCP forwarding considerations:**
    - If using DHCP forwarding on the router, ensure that the rack servers on the VLAN can still communicate with the DHCP server.

By following these steps, users can troubleshoot and resolve issues with VLAN utilization on rack controllers in MAAS, ensuring proper network configuration and connectivity.

## Releasing old DHCP leases

**Problem:**
Deploying servers in MAAS results in an error stating "No more IPs available in subnet," despite having unused IP addresses.

**Solution:**
To release old DHCP leases and resolve IP allocation issues, follow these steps:

1. **Check for orphaned IP addresses:**
   - Run the following SQL query to identify orphaned IP addresses in the MAAS database:
     ```sql
     sudo -u postgres psql -d maasdb -c "
     SELECT count(*)
     FROM maasserver_staticipaddress
     LEFT JOIN maasserver_interface_ip_addresses ON maasserver_staticipaddress.id = maasserver_interface_ip_addresses.staticipaddress_id
     LEFT JOIN maasserver_interface ON maasserver_interface.id = maasserver_interface_ip_addresses.interface_id
     WHERE maasserver_staticipaddress.ip IS NULL 
       AND maasserver_interface.type = 'unknown' 
       AND maasserver_staticipaddress.alloc_type = 6;
     "
     ```
   - This will help you identify any orphaned addresses that are not properly allocated.

2. **Clean neighbor discoveries:**
   - Use the MAAS CLI to clear discovered neighbors, which might be causing IP conflicts:
     ```bash
     maas admin discoveries clear all=True -k
     ```

3. **Verify cleared discoveries:**
   - After clearing, check if the discoveries were successfully removed:
     ```bash
     maas admin discoveries read -k
     ```

4. **Clear ARP table (optional):**
   - If necessary, clear the ARP table on the Rack server to ensure no stale entries exist:
     ```bash
     arp -d [IP address]
     ```
   - Example to clear all entries:
     ```bash
     arp -d 172.21.68.79
     arp -d 172.21.68.69
     ```

5. **Run deployment again:**
   - Attempt to deploy the server again to check if the issue persists. If the error still occurs, check the discoveries once more without cleaning:
     ```bash
     maas admin discoveries read -k
     ```

By following these steps, users can release old DHCP leases and address IP exhaustion issues in MAAS, ensuring successful server deployment.

## Configuring loopback addresses

**Problem:**
Configuring the loopback interface (lo) using MAAS is not straightforward, especially when deploying nodes for use with Free Range Routing (FRR) and BGP.

**Solution:**
To configure loopback addresses in MAAS, follow these steps:

1. **Understand loopback interface:**
   - Loopback interfaces do not require MAC addresses since they are used for internal routing within the node itself.

2. **Manually add loopback interface:**
   - After commissioning a node, manually add the loopback interface in MAAS.
   - If the MAAS web UI requires a MAC address for the loopback interface, use a placeholder value like `00:00:00:00:00:00` but ensure it does not conflict with other nodes.

3. **Avoid duplicate MAC addresses:**
   - Since MAAS does not support duplicate MAC addresses, manually configure the loopback interface on each node with a unique identifier or find a way to bypass the MAC address requirement.

4. **Alternative methods:**
   - If manually adding the loopback interface in MAAS is problematic, consider configuring the loopback interface outside of MAAS using post-deployment scripts.
   - Use MAAS to deploy the base configuration, then apply custom network configurations (including loopback interfaces) through cloud-init or other automation tools.

5. **Feedback from support:**
   - Internal support teams may have additional methods or patches to address this issue. Reach out to MAAS support for the latest solutions or updates regarding loopback interface configuration.

By following these steps, users can effectively configure loopback interfaces on nodes managed by MAAS, facilitating advanced network setups like L3 routing and BGP.

## Shrinking dynamic IP range

**Problem:**
Users may encounter errors when attempting to shrink the dynamic IP address range in MAAS due to conflicts with existing IP addresses or ranges.

**Solution:**
To troubleshoot and resolve this issue, follow these steps:

1. **Check current IP ranges and static addresses:**
   - Use the following SQL queries to check the current IP ranges and static IP addresses in the MAAS database:
     ```sql
     SELECT * FROM maasserver_iprange;
     SELECT * FROM maasserver_staticipaddress WHERE text(ip) LIKE '192.168.0.%' ORDER BY ip;
     ```
   - Identify any existing IP addresses that may conflict with the desired new range.

2. **Identify sticky addresses:**
   - Identify any sticky addresses within the current range that may cause conflicts. Sticky addresses are IP addresses allocated by MAAS DHCP that persist over reboots.

3. **Adjust IP range:**
   - Ensure that the new IP range does not overlap with any existing reserved or sticky addresses. Modify the start and end IP addresses to avoid conflicts.
   - Example: If the current range is 192.168.0.194 - 192.168.0.220 and sticky addresses occupy 192.168.0.195 - 192.168.0.211, adjust the range to avoid these addresses.

4. **Update MAAS configuration:**
   - After identifying a non-conflicting range, update the MAAS configuration to reflect the new IP range.

5. **Database updates:**
   - If necessary, manually update the IP range in the MAAS database to ensure consistency. Make sure to backup the database before making any changes.

By following these steps, users can effectively shrink the dynamic IP address range in MAAS without encountering conflicts with existing IP addresses or ranges.

## Overlapping subnets can break deployments

Ensure that your subnets don't overlap to avoid deployment failures. Check and delete any outdated or redundant subnets through the Web UI.

## Need to reconfigure server IP address

If you need to modify your MAAS server's IP, simply re-run the setup:

```nohighlight
sudo dpkg-reconfigure maas-region-controller
```

## Network booting IBM Power servers

IBM Power servers with OPAL firmware utilise Petitboot for PXE interactions. For smooth deployment, configure a specific NIC as the network boot device via Petitboot.

## Resolve DNS conflicts between LXD and MAAS

If both MAAS and LXD are managing DNS, disable LXD's DNS and DHCP:

```nohighlight
lxc network set $LXD_BRIDGE_NAME dns.mode=none
lxc network set $LXD_BRIDGE_NAME ipv4.dhcp=false
lxc network set $LXD_BRIDGE_NAME ipv6.dhcp=false
```

## Nodes hang on "Commissioning"

**Timing issues**: Make sure the hardware clocks on your nodes and MAAS server are synchronised.

**Network drivers**: Use Linux-compatible network adaptors if commissioning hangs due to driver issues.

Feel free to contribute additional issues and solutions.

## Command 'packer' not found

When you try to run `packer` or execute a `make` command, you may encounter an error message indicating that `packer` is not installed. The issue can be resolved by [referring to this section](/t/how-to-customise-images/5104).

## Error with `packer`:

```nohighlight
stormrider@neuromancer:~$ packer
Command 'packer' not found...
```

## Error with `make`:

```nohighlight
stormrider@neuromancer:~/mnt/Dropbox/src/git/packer-maas/ubuntu$ make
sudo: packer: command not found...
```

## No rule to make target ...OVMF_VARS.fd

Should you see an error like the one below, you've forgotten to [install a needed dependency](/t/how-to-customise-images/5104).

```nohighlight
make: *** No rule to make target '/usr/share/OVMF/OVMF_VARS.fd'...
```

## Failure to create QEMU driver

Encountering the following error means you're missing a dependency. Refer to [this section](/t/how-to-customise-images/5104) for resolution.

```nohighlight
Failed creating Qemu driver: exec: "qemu-img": executable file not found in $PATH
```

## Timeout changes not taking effect

If you've modified the session timeout settings in the MAAS web interface but don't see the changes, do the following:

1. Make sure you've got administrative access to the MAAS web interface for changing session timeout settings.
2. After altering the session timeout duration, don't forget to save the new settings.
3. Clear your browser's cache and cookies. They might be holding on to old settings. Restart your browser and try again.

## Users logged out before timeout expires

If users are getting logged out before the session timeout you've set, consider these checks:

1. Double-check the unit of time you've set for the session timeout (weeks, days, hours, minutes). A mistake in units can cause unexpected timeouts.
2. Inspect any server settings conflicting with MAAS that may cause premature session timeouts, like window manager logout settings in Ubuntu.
3. If you're using a load balancer or proxy, make sure it's not causing additional timeouts conflicting with MAAS.

## Can't set an infinite session timeout

You can't set an "infinite" session timeout in MAAS. The maximum allowed duration is 14 days. This limit strikes a balance between security and usability.

## Users are suddenly logged out

MAAS will auto-logoff users when the session timeout duration is reached. If this happens more often than desired, consider increasing the timeout value to prevent frequent "idle-time" logouts.

## Can't set different timeouts for user groups

MAAS only supports a global session timeout setting. While you can't customise this by user group, you could deploy separate MAAS instances with different configurations to achieve similar effects.

## Can't extend sessions beyond the timeout

The timeout duration resets every time there's activity from the user. To extend a session, simply refresh the page before the timeout period ends. This will reset the session timer.

## Django errors

Sometimes, you may face the following Django error:

```nohighlight
django.core.exceptions.ValidationError: ['Subarchitecture(<value>) must be generic when setting hwe_kernel.']
```

To solve this, try specifying a different commissioning kernel—perhaps upgrading from Xenial to Focal.

## Forgotten password

If you forget your MAAS admin password but have sudo privileges, you can reset it like so:

```nohighlight
sudo maas changepassword $PROFILE
```

Replace `$PROFILE` with the username.

## Missing Web UI

The default MAAS web UI is at `http://<hostname>:5240/MAAS/`. If it's unreachable:

- Verify Apache is running: `sudo /etc/init.d/apache2 status`.
- Validate the hostname or try `http://127.0.0.1:5240/MAAS/`.

## Backdoor image login

Ephemeral images boot nodes during MAAS activities. If you need emergency access, you can create a temporary backdoor in these images. This lets you log in to check logs and debug issues.

## Extract the cloud image

Download the appropriate image and extract its files:

```nohighlight
wget https://cloud-images.ubuntu.com/xenial/current/xenial-server-cloudimg-amd64-root.tar.gz
mkdir xenial
sudo tar -C xenial -xpSf xenial-server-cloudimg-amd64-root.tar.gz --numeric-owner --xattrs "--xattrs-include=*"
```

## Generate password hash

Create a SHA-512 hashed password:

```nohighlight
python3 -c 'import crypt; print(crypt.crypt("ubuntu", crypt.mksalt(crypt.METHOD_SHA512)))'
```

Modify the `xenial/etc/shadow` file to insert this hash.

## Rebuild squashfs image

Create a new SquashFS file with your changes:

```nohighlight
sudo mksquashfs xenial/ xenial-customized.squashfs -xattrs -comp xz
```

Replace the existing MAAS image with this customised one.

## Migrating snap installs

For snap-based MAAS in 'all' mode, you can migrate to a local PostgreSQL:

```nohighlight
sudo /snap/maas/current/helpers/migrate-vd Snapatabase
```

## Manual DB export

To manually move your MAAS database, run:

```nohighlight
export PGPASS=$(sudo awk -F':\\s+' '$1 == "database_pass" {print $2}' \
    /var/snap/maas/current/regiond.conf)
sudo pg_dump -U maas -h /var/snap/maas/common/postgres/sockets \
    -d maasdb -F t -f maasdb-dump.tar
```

Stop the MAAS snap (`sudo snap stop maas`) and create a new PostgreSQL user and database for MAAS on the destination machine.

This should cover various miscellaneous issues you may encounter while using MAAS. Feel free to contribute with your own experiences.

## Leaked admin API key

If MAAS hardware sync leaks your admin API key, you can:

- Rotate all admin tokens
- Re-deploy machines with hardware sync enabled

Or swap the token manually:

## Manually swap the MAAS admin API token

Query the database to identify machines with hardware sync enabled:

```nohighlight
select system_id 
from maasserver_node 
where enable_hw_sync = true;
```

Rotate API keys on any affected machines. To verify an API key belongs to an admin, perform this database query:

```nohighlight
select u.username, u.email 
from auth_user u
left join piston3_consumer c 
on u.id = c.user_id
where key = 'your-leaked-api-key';
```

To remove the leaked API key, log in to the MAAS UI and delete it. Then reconfigure your MAAS CLI and hardware sync as needed.
