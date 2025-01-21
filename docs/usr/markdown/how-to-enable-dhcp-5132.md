> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/enabling-dhcp" target = "_blank">Let us know.</a>

This page explains how to manage DHCP for MAAS.  If you're new to the subject, you might find it helpful to first read an [overview of MAAS DHCP](/t/about-dhcp-in-maas/6682).

## Enable MAAS DHCP (UI)

To enable MAAS-managed DHCP via the MAAS UI:

1. Select *Subnets* > <desired VLAN> > *Reserved ranges* > *Reserved dynamic range*.

2. Enter a *Start IP address* and an *End IP address*.

3. Select *Reserve* > *Configure DHCP*. You will see a new screen.

4. The options *MAAS provides DHCP* and *Provide DHCP from a rack controller* will be pre-selected.

5. If you accept these options, you may need to choose a *Rack controller*.

6. If you choose *Relay to another VLAN*, you will need to choose the target VLAN.

7. Under *Reserved dynamic range*, you may have to select a subnet from the drop-down.

8. Select *Configure DHCP* for your changes to be registered with MAAS.

## Create an IP range (UI)

To create an IP range:

1. Select *Subnets*.

2. In the *SUBNET* column, choose the subnet for which you want to create an IP range.

3. Scroll down to *Reserved ranges*.

4. Select *Reserve range* and choose either *Reserve range* or *Reserve dynamic range*. Note that if you choose a dynamic range, MAAS will automatically provide DHCP for enlistment and commissioning provided that the associated VLAN has DHCP enabled. 

5. A window will appear, allowing you to enter a *Start IP address* and *End IP address

6. If you didn't select a dynamic range, you may optionally enter a *Purpose* for the range.

6. Select *Reserve* to register your choices with MAAS.

## Edit an IP range (UI)

1. Select *Menu* at the far right of the row corresponding to the subnet in question.

2. Select *Edit reserved range* from the menu that appears. 

3. Edit the fields as desired.

4. Select *Save* to register your changes.

## Delete IP range (UI)

To delete an IP range, select *Menu* at the far right of the subnet row; then choose *Remove range* > *Save*.

## Extend IP range (UI)

To extend a dynamic IP range, select *Subnets* > subnet > *Reserve dynamic range*. DHCP will be enabled automatically.

## Enable DHCP (CLI)

To enable DHCP on a VLAN in a certain fabric, enter the following command:

```nohighlight
maas $PROFILE vlan update $FABRIC_ID $VLAN_TAG dhcp_on=True \
    primary_rack=$PRIMARY_RACK_CONTROLLER
```

To enable DHCP HA, you will need both a primary and a secondary controller:

```nohighlight
maas $PROFILE vlan update $FABRIC_ID $VLAN_TAG dhcp_on=True \
    primary_rack=$PRIMARY_RACK_CONTROLLER \
    secondary_rack=$SECONDARY_RACK_CONTROLLER 
```

>*Pro tip*: You must enable DHCP for PXE booting on the 'untagged' VLAN.

You will also need to set a default gateway:

```nohighlight
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
```
## Set up a DHCP relay

Via the MAAS UI, you can set up a DHCP relay from one VLAN (source) to another VLAN (target) as follows:

1. Ensure the target VLAN has DHCP enabled.

2. Set up the external relay. This relay is set up independently from MAAS. See [DHCP relay](/t/reference-maas-glossary/5416) for software suggestions.

3. Configure MAAS-managed DHCP as normal.

4. Navigate to the source VLAN page.

5. Select the *Relay DHCP* action. 

5. Fill in the fields in the resulting form. Note that the crucial setting is the target VLAN (*Relay VLAN*). 

6. Select *Relay DHCP* to finish.

To use the MAAS CLI to relay DHCP traffic for a VLAN (source) through another VLAN (target):

```nohighlight
maas $PROFILE vlan update $FABRIC_ID $VLAN_VID_SRC relay_vlan=$VLAN_ID_TARGET
```

For example, to relay VLAN with vid 0 (on fabric-2) through VLAN with id 5002 :

```nohighlight
maas $PROFILE vlan update 2 0 relay_van=5002
```

## Managing DHCP snippets (UI) 

To manage snippets via the MAAS UI as an administrator, select *Settings >> DHCP snippets*.

## Search snippets (UI)

To search DHCP snippets, enter the text to match in *Search DHCP snippets*. MAAS will progressively update the list of snippets as you type your search terms.

## Add snippets (UI)

To add a snippet:

1. Select *Add snippet*.

2. Enter the *Snippet name*.

3. Optionally, check *Enabled* to enable the snippet now. Note that MAAS will not apply the snippet unless it is enabled.

4. Optionally, enter a *Description* for the snippet.

5. Optionally, choose a *Type* for the snippet from the drop-down (defaults to *Global*). This parameter sets the scope of the snippet. Note that if you choose a type other than global, you may need to choose the specific scope. For example, if you choose the *Subnet* type, you must identify the specific subnet to which this snippet applies.

6. Enter the *DHCP snippet*. This is not validated on entry.

7. Select *Save snippet* to register your changes with MAAS

## Edit snippets (UI)

To edit a snippet, select the pencil icon to the right of the snippet row and edit the fields as desired.

## Delete snippets (UI)

To delete a snippet, select the trash can icon to the right of the snippet. You will be asked to confirm; be aware that once confirmed, this action cannot be undone.

## Create global DHCP snippets (CLI)

To create a **global** snippet:

```nohighlight
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME \
    value=$DHCP_CONFIG description=$DHCP_SNIPPET_DESCRIPTION \
    global_snippet=true
```

## Create subnet snippets (CLI)

To create a **subnet** snippet:

```nohighlight
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME \
    value=$DHCP_CONFIG description=$DHCP_SNIPPET_DESCRIPTION \
    subnet=$SUBNET_ID
```

## Create node snippets (CLI)

To create a **node** snippet:

```nohighlight
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME \
    value=$DHCP_CONFIG description=$DHCP_SNIPPET_DESCRIPTION \
    node=$NODE_ID
```

## List snippets (CLI)

To list all snippets (and their characteristics) in the MAAS:

```nohighlight
maas $PROFILE dhcpsnippets read
```

To list a specific snippet:

```nohighlight
maas $PROFILE dhcpsnippet read id=$DHCP_SNIPPET_ID
```

The snippet name can also be used instead of its ID:

```nohighlight
maas $PROFILE dhcpsnippet read name=$DHCP_SNIPPET_NAME
```

## Update snippets (CLI)

To update a DHCP snippet attribute:

```nohighlight
maas $PROFILE dhcpsnippet update $DHCP_SNIPPET_ID <option=value>
```

You can also use a snippet name instead of its ID.

## Toggle a snippet (CLI)

Enabling and disabling a snippet is considered a snippet update and is done via a Boolean option ('true' or 'false'). You can disable a snippet like this:

```nohighlight
maas $PROFILE dhcpsnippet update $DHCP_SNIPPET_ID enabled=false
```

When you disable a snippet, MAAS removes the text you added to the dhcpd.conf file when you created the snippet.

## Delete a snippet (CLI)

To delete a snippet:

```nohighlight
maas $PROFILE dhcpsnippet delete $DHCP_SNIPPET_ID
```

You can also use a snippet name in place of its ID.

## Create an IP range (CLI)

To create a range of dynamic IP addresses that will be used by MAAS for node enlistment, commissioning, and possibly deployment:

```nohighlight
maas $PROFILE ipranges create type=dynamic \
    start_ip=$IP_DYNAMIC_RANGE_LOW end_ip=$IP_DYNAMIC_RANGE_HIGH \
    comment='This is a reserved dynamic range'
```
## Protect a range (CLI)

To create a range of IP addresses that will not be used by MAAS:

```nohighlight
maas $PROFILE ipranges create type=reserved \
    start_ip=$IP_STATIC_RANGE_LOW end_ip=$IP_STATIC_RANGE_HIGH \
    comment='This is a reserved range'
```

## Protect an IP (CLI)

To reserve a single IP address that will not be used by MAAS:

```nohighlight
maas $PROFILE ipaddresses reserve ip_address=$IP_STATIC_SINGLE
```

## Edit a range (CLI)

To edit an IP range:

1. Find the ID of the desired IP range with the command:

```nohighlight
maas admin ipranges read
```

2. Edit the range with the command:

```nohighlight
maas admin iprange update $ID start_ip="<start ip>" end_ip="<end ip>" comment="freeform comment"
```

This command will update the IP range associated with $ID.

## Delete a range (CLI)

You can delete a range of IP addresses by deleting the addresses one by one. To remove a single reserved IP address:

```nohighlight
maas $PROFILE ipaddresses release ip=$IP_STATIC_SINGLE
```

## Create A/AAAA DNS records (CLI)

An administrator can create an A record when creating a DNS resource with an IPv4 address:

```nohighlight
mass $PROFILE dnsresources create fqdn=$HOSTNAME.$DOMAIN ip_addresses=$IPV4ADDRESS
```

An administrator can also create an AAAA record when creating a DNS resource with an IPv6 address:

```nohighlight
mass $PROFILE dnsresources create fqdn=$HOSTNAME.$DOMAIN ip_addresses=$IPV6ADDRESS
```

## Set CNAME DNS records (CLI)

An administrator can set a DNS Alias (CNAME record) to an already existing DNS entry of a machine:

```nohighlight
mass $PROFILE dnsresource-records create fqdn=$HOSTNAME.$DOMAIN rrtype=cname rrdata=$ALIAS
```

For example, to set `webserver.maas.io` to alias to `www.maas.io`:

```nohighlight
maas $PROFILE dnsresource-records create fqdn=webserver.maas.io rrtype=cname rrdata=www
```

## Set ME DNS records (CLI)

An administrator can set a DNS Mail Exchange pointer record (MX and value) to a domain:

```nohighlight
maas $PROFILE dnsresource-records create fqdn=$DOMAIN rrtype=mx rrdata='10 $MAIL_SERVER.$DOMAIN'
```

For example, to set the domain.name managed by MAAS to have an MX record and that you own the domain:

```nohighlight
maas $PROFILE dnsresource-records create fqdn=maas.io rrtype=mx rrdata='10 smtp.maas.io'
```

## Set a DNS forwarder

To set a DNS forwarder:

```nohighlight
maas $PROFILE maas set-config name=upstream_dns value=$MY_UPSTREAM_DNS
```