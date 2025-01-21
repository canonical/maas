In MAAS-managed networks, you can further manage your subnets with a reserved range of IP addresses.  You can reserve IP addresses by adding one or more reserved ranges to a subnet configuration. You can define two types of ranges: reserved ranges and reserved dynamic ranges.  

## What is a reserved range?

A reserved range in MAAS refers to a block of IP addresses that are set aside and not allocated automatically by MAAS. This can be useful in scenarios where you want to manually manage IP addresses for specific purposes, such as for critical services, static IPs for certain servers, or integration with other systems like OpenStack.

A reserved range operates differently depending on whether the subnet is managed or unmanaged.  For a managed (subnet), MAAS will never assign IP addresses inside this range.  You can use this range for anything, such as infrastructure systems, network hardware, external DHCP, or an OpenStack namespace.  For an unmanaged (subnet), MAAS will only assign IP addresses inside this range -- but MAAS can assign any IP within this range.

A reserved dynamic range is used by MAAS for enlisting, commissioning and, if enabled, MAAS-managed DHCP on the machine's VLAN during commissioning and deployment. If created with the Web UI, an initial range is created as part of the DHCP enablement process. MAAS never uses IP addresses from this range for an unmanaged subnet.

## Reserved ranges and OpenStack

In an OpenStack environment, you might need to reserve IP ranges for specific services such as the management network, storage network, or tenant networks. By reserving these IP ranges in MAAS, you can ensure that these critical addresses are not allocated to other devices, preventing IP conflicts and ensuring reliable network operation.

This article gives specific instructions about creating and managing IP ranges.

## How to create a reserved range in MAAS (UI)

To set up a reserved range in MAAS (Metal as a Service), you can follow these steps. This guide will also help you understand what a reserved range is and how it is used, especially in the context of OpenStack.

1. Log in to the MAAS Web UI: Open your web browser and navigate to your MAAS server. Log in with your MAAS credentials.

2. Navigate to the subnets page:
Click on the "Subnets" tab in the top navigation bar. This will show you a list of all subnets that MAAS is managing.

3. Select the subnet:
Find the subnet where you want to create the reserved range and click on it. This will open the subnet details page.

4. Go to reserved ranges:
In the subnet details page, look for the "Reserved Ranges" section. This is usually located below the list of IP addresses.

5. Add a reserved range:
Click on the "Add Reserved Range" button. This will open a form to define the new reserved range.

6. Define the range:

   - Start IP: Enter the starting IP address of the range you want to reserve.
   - End IP: Enter the ending IP address of the range you want to reserve.
   - Purpose: Optionally, you can add a description or purpose for this reserved range to help identify its use.
   - Save the range:

    After filling in the details, click on the "Save" button to create the reserved range.

7. Verify the reserved range:
Once saved, you should see the new reserved range listed in the "Reserved Ranges" section. This range will now be excluded from automatic IP allocation by MAAS.

# How to create a dynamic IP range in MAAS (CLI)

To create a range of dynamic IP addresses that will be used by MAAS for node enlistment, commissioning, and possibly deployment:

```nohighlight
maas $PROFILE ipranges create type=dynamic \
    start_ip=$IP_DYNAMIC_RANGE_LOW end_ip=$IP_DYNAMIC_RANGE_HIGH \
    comment='This is a reserved dynamic range'
```

To create a range of IP addresses that will not be used by MAAS:

```nohighlight
maas $PROFILE ipranges create type=reserved \
    start_ip=$IP_STATIC_RANGE_LOW end_ip=$IP_STATIC_RANGE_HIGH \
    comment='This is a reserved range'
```

To reserve a single IP address that will not be used by MAAS:

```nohighlight
maas $PROFILE ipaddresses reserve ip_address=$IP_STATIC_SINGLE
```

To remove such a single reserved IP address:

```nohighlight
maas $PROFILE ipaddresses release ip=$IP_STATIC_SINGLE
```

## How to edit an existing IP range (UI)

Click the 'Menu' button at the far right of the row corresponding to the subnet in question and select 'Edit reserved range' from the menu that appears. Edit the fields as desired and click the 'Save' button.

## How to edit an existing IP range (CLI)

To edit an IP range, first find the ID of the desired IP range with the command:

```nohighlight
maas admin ipranges read
```

Examine the JSON output to find the ID corresponding to the IP range you want to edit, then enter:

```nohighlight
maas admin iprange update $ID start_ip="<start ip>" end_ip="<end ip>" comment="freeform comment"
```

This command will update the IP range associated with $ID.

## How to delete an existing IP range (UI only)

Select 'Remove range' from the menu that appears when clicking the 'Menu' button at the far right of the row corresponding to the subnet in question.