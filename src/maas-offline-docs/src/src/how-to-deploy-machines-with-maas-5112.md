> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/deploying-machines-in-maas" target = "_blank">Let us know.</a>*

This page explains how to deploy machines with MAAS.  You may also want to learn [how images get deployed](/t/about-machines/6695).

## Deploy machines

To deploy allocated machines in MAAS:

* In the MAAS UI, select *Machines* > machine(s) > *Take action* > *Deploy* > *Deploy machines*. While a machine is deploying its status will change to Deploying to 'OS', where 'OS' is the name of the OS being deployed (e.g. 'Deploying to Ubuntu 16.04 LTS'). Once a machine has finished deploying its status will change to just the name of the OS (e.g. 'Ubuntu 18.04 LTS').

* Via the MAAS CLI, execute the following commands:

```nohighlight
    maas $PROFILE machine deploy $SYSTEM_ID
```
    
    To deploy a node as a KVM host:
    
```nohighlight
    maas $PROFILE machine deploy $SYSTEM_ID install_kvm=True
```

## Deploy an ephemeral OS (MAAS 3.5)

If you wish to deploy an ephemeral OS, select *Deploy in memory* when preparing to deploy the machine.

> Note that networking for ephemeral OS images is only set up for Ubuntu images. For non-Ubuntu images, you only get the PXE interface set up to do DHCP against MAAS. All other interfaces need to be configured manually after deployment.

## Set deployment timeout (CLI)

By default, when you deploy a machine, MAAS will consider the deployment a failure if it doesn't complete within 30 minutes. You can configure this timeout, if you wish, with the command:

```nohighlight
maas $PROFILE maas set-config name=node-timeout value=$NUMBER_OF_MINUTES
```

## Add running machines (CLI)

Via the API/CLI, you can create a machine, passing the deployed flag:

```nohighlight
$ maas $profile machines create deployed=true hostname=mymachine \   
architecture=amd64 mac_addresses=00:16:3e:df:35:bb power_type=manual
```

## Add a running machine from the machine itself

On the machine itself (the recommended way, if the machine is running Ubuntu), you can download a helper script from MAAS and create the machine that way:

```nohighlight
$ wget http://$MAAS_IP:5240/MAAS/maas-run-scripts
$ chmod 755 maas-run-scripts
$ ./maas-run-scripts register-machine --hostname mymachine \
 > http://$MAAS_IP:5240/MAAS $MAAS_API_TOKEN
```

Now you have a machine in MAAS that’s in the deployed state, with no hardware information yet.