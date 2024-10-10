> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/try-out-the-maas-cli" target = "_blank">Let us know.</a>*

This tutorial will walk you through the basics of the MAAS CLI.

## Log in

1. **Fetch your API key**: Generate your unique key with the following command:

```nohighlight
    maas apikey --username=$MAAS_USER > api-key
```
   
2. **Login**: Use your API key to authenticate:

```nohighlight
    maas login admin http://<maas.domain>:5240/MAAS/api/2.0/ < api-key
```

## Configure MAAS

1. **Set the DNS forwarder**: If it's your first time, set up DNS forwarding:

```nohighlight
    maas $MAAS_USER maas set-config name=upstream_dns value=8.8.8.8
```

2. **Import Ubuntu images**: Again, if new, pull in Ubuntu images:

```nohighlight
    maas $MAAS_USER boot-resources import
```

## Manage nodes

1. **Enlist a node**: Add a new machine to MAAS:

```nohighlight
    maas $MAAS_USER machines create architecture=amd64 \
      power_type=virsh mac_addresses=52:54:00:00:00:01
```

2. **Review status**: Confirm the node’s state:

```nohighlight
    maas $MAAS_USER machines read | jq '.[].status_name' 
```

3. **Commission a node**: Prepare the node for deployment:

```nohighlight
    maas $MAAS_USER machine commission <node_id>
```

4. **Acquire a node**: Claim the commissioned node:

```nohighlight
    maas $MAAS_USER machines allocate system_id=<id>
```

5. **Deploy a node**: Get the machine running:

```nohighlight
    maas $MAAS_USER machine deploy <id>
```

## Connect nodes

1. **Fetch a node's IP**: Retrieve the IP of a deployed node:

```nohighlight
    lxc list
```

2. **Gain SSH access**: Just log in as `ubuntu`.

3. **File transfer**: Use `scp` for transferring files, and apply your customisations.

## Explore more

- [Craft custom images](/t/tutorial-creating-custom-images/6102)
- [Delve into advanced network settings](/t/how-to-connect-maas-networks/5164)
- [Get creative with LXD containers](/t/how-to-set-up-external-lxd/5208)
