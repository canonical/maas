This page explains how to use LXD projects with MAAS.

## Create a new LXD project

If you're using MAAS from the CLI, you'll want to make sure you've generated an API key and logged in before you attempt to create a VM host. These steps are fairly simple; first, you'll need the MAAS URL, which for this example, is `http://192.168.33.91:5240/MAAS`.  You can find this URL by typing:

```nohighlight
$ maas --help
```

This will return a help string. The correct MAAS API URL is shown in the last entry, "admin:"

```nohighlight
usage: maas [-h] COMMAND ...

optional arguments:
  -h, --help      show this help message and exit

drill down:
  COMMAND
    login         Log in to a remote API, and remember its description and credentials.
    logout        Log out of a remote API, purging any stored credentials.
    list          List remote APIs that have been logged-in to.
    refresh       Refresh the API descriptions of all profiles.
    init          Initialise MAAS in the specified run mode.
    config        View or change controller configuration.
    status        Status of controller services.
    migrate       Perform migrations on connected database.
    apikey        Used to manage a user's API keys. Shows existing keys unless --generate or --delete
                  is passed.
    configauth    Configure external authentication.
    createadmin   Create a MAAS administrator account.
    changepassword
                  Change a MAAS user's password.
    admin         Interact with http://192.168.33.91:5240/MAAS/api/2.0/
```

Next, you'll need to generate the API key for your administrative user. You can this by entering the following at the command line:

```nohighlight
$ sudo maas apikey --generate --username admin
[sudo] password for $USERNAME:
```

This will return only the API key, which looks something like this:

```nohighlight
PPWQWHs75G6rRmhgdQ:mskfQUYsSqBQnfCYC8:ZruUD3EmnQyhRLapR5whY4bV4h8n7zr7
```

Having both of these, you can login with the following command:

```nohighlight
$ maas login admin http://192.168.33.91:5240/MAAS/api/2.0
API key (leave empty for anonymous access): PPWQWHs75G6rRmhgdQ:mskfQUYsSqBQnfCYC8:ZruUD3EmnQyhRLapR5whY4bV4h8n7zr7
```

Note in this example, you could cut and paste both the MAAS API URL and the API key into the command, at appropriate points. When you log in successfully, you will obtain a help listing something like this:

```nohighlight

You are now logged in to the MAAS server at
http://192.168.33.91:5240/MAAS/api/2.0/ with the profile name 'admin'.

For help with the available commands, try:

  maas admin --help
```

Now that you're logged in, you can create a new KVM with the following `maas $PROFILE vm-hosts create` command:

```nohighlight
$ maas admin vm-hosts create --help
usage: maas admin vm-hosts create [--help] [-d] [-k] [data [data ...]]

Create a VM host


This method accepts keyword arguments. Pass each argument as a
key-value pair with an equals sign between the key and the value:
key1=value1 key2=value key3=value3. Keyword arguments must come after
any positional arguments.

Create or discover a new VM host.

:param type: Required. The type of VM host to create:
``lxd`` or ``virsh``.
:type type: String

 :param power_address: Required. Address that gives
MAAS access to the VM host power control. For example, for virsh
``qemu+ssh:-172.16.99.2#,system``
For ``lxd``, this is just the address of the host.
:type power_address: String

 :param power_user: Required. Username to use for
power control of the VM host. Required for ``virsh``
VM hosts that do not have SSH set up for public-key authentication.
:type power_user: String

 :param power_pass: Required. Password to use for
power control of the VM host. Required ``virsh`` VM hosts that do
not have SSH set up for public-key authentication and for ``lxd``
if the MAAS certificate is not registered already in the LXD server.
:type power_pass: String

 :param name: Optional. The new VM host's name.
:type name: String

 :param zone: Optional. The new VM host's zone.
:type zone: String

 :param pool: Optional. The name of the resource
pool the new VM host will belong to. Machines composed from this VM host
will be assigned to this resource pool by default.
:type pool: String

 :param tags: Optional. A tag or list of tags (
comma delimited) to assign to the new VM host.
:type tags: String

 :param project: Optional. For ``lxd`` VM hosts, the
project that MAAS will manage. If not provided, the ``default`` project
will be used. If a nonexistent name is given, a new project with that
name will be created.
:type project: String


Common command-line options:
    --help, -h
	Show this help message and exit.
    -d, --debug
	Display more information about API responses.
    -k, --insecure
	Disable SSL certificate check
stormrider@wintermute:~$ maas admin vmho
```

In the case of our example server, you'd type:

```nohighlight
$ maas admin vm-hosts create type=lxd power_address=10.196.199.1:8443 project=keystone name=foo
```

You'd be greeted with a success result that looks something like this:

```nohighlight
Success.
Machine-readable output follows:
{
    "host": {
        "system_id": "hybned",
        "__incomplete__": true
    },
    "storage_pools": [
        {
            "id": "default",
            "name": "default",
            "type": "dir",
            "path": "/var/snap/lxd/common/lxd/storage-pools/default",
            "total": 248618848256,
            "used": 0,
            "available": 248618848256,
            "default": true
        },
        {
            "id": "default2",
            "name": "default2",
            "type": "dir",
            "path": "/var/snap/lxd/common/lxd/storage-pools/default2",
            "total": 248618848256,
            "used": 0,
            "available": 248618848256,
            "default": false
        }
    ],
    "type": "lxd",
    "used": {
        "cores": 0,
        "memory": 0,
        "local_storage": 0
    },
    "zone": {
        "name": "default",
        "description": ",
        "id": 1,
        "resource_uri": "/MAAS/api/2.0/zones/default/"
    },
    "total": {
        "cores": 0,
        "memory": 0,
        "local_storage": 497237696512
    },
    "tags": [
        "pod-console-logging"
    ],
    "architectures": [
        "amd64/generic"
    ],
    "available": {
        "cores": 0,
        "memory": 0,
        "local_storage": 497237696512
    },
    "pool": {
        "name": "default",
        "description": "Default pool",
        "id": 0,
        "resource_uri": "/MAAS/api/2.0/resourcepool/0/"
    },
    "default_macvlan_mode": null,
    "name": "foo",
    "version": "4.13",
    "id": 26,
    "memory_over_commit_ratio": 1.0,
    "cpu_over_commit_ratio": 1.0,
    "capabilities": [
        "composable",
        "dynamic_local_storage",
        "over_commit",
        "storage_pools"
    ],
    "resource_uri": "/MAAS/api/2.0/vm-hosts/26/"
}
```

Note that we specified the project `keystone` as part of this creation step. We can now check the LXD project list and see if we did, in fact, create that project:

```nohighlight
$ lxc project list
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
|        NAME         | IMAGES | PROFILES | STORAGE VOLUMES | NETWORKS |       DESCRIPTION       | USED BY |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| default             | YES    | YES      | YES             | YES      | Default LXD project     | 5       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| keystone            | NO     | YES      | NO              | NO       | Project managed by MAAS | 1       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| maas_vm_host_001    | YES    | YES      | YES             | NO       |                         | 1       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| new_project         | NO     | YES      | NO              | NO       | Project managed by MAAS | 1       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| not-maas (current)  | YES    | YES      | YES             | NO       |                         | 3       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| pg-basebackup-tests | NO     | YES      | NO              | NO       | Project managed by MAAS | 16      |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
```

Finally, we can switch to the project to get a detailed look:

```nohighlight
$ lxc project switch keystone
$ lxc list
+------+-------+------+------+------+-----------+
| NAME | STATE | IPV4 | IPV6 | TYPE | SNAPSHOTS |
+------+-------+------+------+------+-----------+
```

You'll note that, since we just created the VM host, without adding any VMs, the `keystone` project will be empty.

## Create a new VM in a project

Let's say that you have created your VM host (called `foo`, in this case) with a new, empty project called `keystone`. Now you want to create (that is, compose) a VM is this project. You can accomplish this with a command similar to the following:

```nohighlight
maas admin vm-host compose 26
```

The VM host ID is found from the `resource_uri` line of the JSON output that was returned when you created the VM host; in this case, that line looks like this, yielding the ID number `26`:

```nohighlight
    "resource_uri": "/MAAS/api/2.0/vm-hosts/26/"
```

MAAS will create (compose) the VM and immediately commission it. You can see this by executing the following command:

```nohighlight
maas admin machines read wx8xcr | grep status_name
```

In this example, we're using the system ID returned as the `resource_uri` of the composed VM that was returned in the JSON from the `maas admin vm-host compose` command above. We receive output similar to the following:

```nohighlight
    "network_test_status_name": "Unknown",
    "testing_status_name": "Passed",
    "status_name": "Ready",
    "commissioning_status_name": "Passed",
    "other_test_status_name": "Unknown",
    "storage_test_status_name": "Passed",
    "interface_test_status_name": "Unknown",
    "cpu_test_status_name": "Unknown",
    "memory_test_status_name": "Unknown",
```

You can see by the several status messages that this machine was successfully commissioned, sitting now in the ready state.

So from this experiment, we can see that creating (composing) a VM in a VM host causes MAAS to automatically commission the VM.

## Move a VM to a project

We've seen what happens if we compose a VM in a VM host -- it's automatically commissioned. But what if we move an existing VM into a LXD project that's associated with a MAAS VM host?  Let's try it and see.

First, let's check on an existing VM in one of our other projects:

```nohighlight
$ lxc project switch not-maas
$ lxc list
+-----------------+---------+------+------+-----------------+-----------+
|      NAME       |  STATE  | IPV4 | IPV6 |      TYPE       | SNAPSHOTS |
+-----------------+---------+------+------+-----------------+-----------+
| trusty-drake    | STOPPED |      |      | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+------+-----------------+-----------+
| upward-stallion | STOPPED |      |      | CONTAINER       | 0         |
+-----------------+---------+------+------+-----------------+-----------+
$ lxc move trusty-drake trusty-drake --project not-maas --target-project keystone
$ lxc project switch keystone
$ lxc list
+--------------+---------+------+------+-----------------+-----------+
|     NAME     |  STATE  | IPV4 | IPV6 |      TYPE       | SNAPSHOTS |
+--------------+---------+------+------+-----------------+-----------+
| handy-sloth  | STOPPED |      |      | VIRTUAL-MACHINE | 0         |
+--------------+---------+------+------+-----------------+-----------+
| trusty-drake | STOPPED |      |      | VIRTUAL-MACHINE | 0         |
+--------------+---------+------+------+-----------------+-----------+
```

We can check the status with MAAS, but we'll find that the machine isn't recognised. If we turn it on, it will be enlisted by MAAS. Since MAAS doesn't know about it yet, we need to turn it on with the following command:

```nohighlight
lxc start trusty-drake
```

Nothing happens for a while, but eventually MAAS will discover the machine and attempt to commission it. In fact, since MAAS doesn't know what power type to use, it completes all the commissioning scripts except `30-maas-01-bmc-config`:

| Name | Tags | Result | Date | Runtime |
|:-----|:----:|:------:|:-----|--------:|
| 20-maas-01-install-lldpd |	node|	Passed|	Mon, 19 Apr. 2021 21:42:22|	0:00:00|
| 20-maas-02-dhcp-unconfigured-ifaces|	node|	Passed|	Mon, 19 Apr. 2021 21:42:22|	0:00:00|
| 30-maas-01-bmc-config|	bmc-config, node|	Skipped|	Mon, 19 Apr. 2021 21:42:22|	0:00:00|
50-maas-01-commissioning| 	node|	Passed|	Mon, 19 Apr. 2021 21:42:23|	0:00:00|
maas-capture-lldpd| 	node|	Passed|	Mon, 19 Apr. 2021 21:43:17|	0:00:53|
maas-get-fruid-api-data| 	node|	Passed|	Mon, 19 Apr. 2021 21:42:26|	0:00:00|
maas-kernel-cmdline| 	node|	Passed|	Mon, 19 Apr. 2021 21:42:25|	0:00:01|
maas-list-modaliases| 	node|	Passed|	Mon, 19 Apr. 2021 21:42:25|	0:00:00|
maas-lshw| 	node|	Passed|	Mon, 19 Apr. 2021 21:42:26|	0:00:02|
maas-serial-ports| 	node|	Passed|	Mon, 19 Apr. 2021 21:42:24|	0:00:00|
maas-support-info| 	node|	Passed|	Mon, 19 Apr. 2021 21:42:25|	0:00:01|

This machine will sit in the "New" state until you assign it a power type, and enter the correct power parameters.

For example, to get this new (moved) VM ready to be fully commissioned, you'll need to first find it in the machine list:

```nohighlight
maas admin machines read
(lots of JSON output, down to the last line)
  "resource_uri": "/MAAS/api/2.0/machines/r3mmsh/"
```

## Hide LXD from MAAS

Suppose that want to use MAAS with your default LXD project, and that you have a couple of LXD entities in your default project that you don't want to use with MAAS:

```nohighlight
$ lxc list
+-----------------+---------+-----------------------+---------------------------------------------+-----------------+-----------+
|      NAME       |  STATE  |         IPV4          |                    IPV6                     |      TYPE       | SNAPSHOTS |
+-----------------+---------+-----------------------+---------------------------------------------+-----------------+-----------+
| trusty-drake    | STOPPED |                       |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+-----------------------+---------------------------------------------+-----------------+-----------+
| upward-stallion | RUNNING | 10.196.199.194 (eth0) | fd42:ec:5a53:59d2:216:3eff:febf:7fa7 (eth0) | CONTAINER       | 0         |
+-----------------+---------+-----------------------+---------------------------------------------+-----------------+-----------+
| witty-lizard    | STOPPED |                       |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+-----------------------+---------------------------------------------+-----------------+-----------+
```

In the above example, you want to use `witty-lizard` with MAAS, but you want to move the other two entities to a project called `not-maas`. To accomplish this, you first need to create the `not-maas` project if it doesn't exist:

```nohighlight
$ lxc project create not-maas
Project not-maas created
$ lxc project list
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
|        NAME         | IMAGES | PROFILES | STORAGE VOLUMES | NETWORKS |       DESCRIPTION       | USED BY |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| default (current)   | YES    | YES      | YES             | YES      | Default LXD project     | 7       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| maas_vm_host_001    | YES    | YES      | YES             | NO       |                         | 1       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| not-maas            | YES    | YES      | YES             | NO       |                         | 1       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| pg-basebackup-tests | NO     | YES      | NO              | NO       | Project managed by MAAS | 16      |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
```

Having done so, you now want to move `trusty-drake` and `upward-stallion` to a new project. Let's tackle `trusty-drake` first:

```nohighlight
$ lxc move trusty-drake trusty-drake --project default --target-project not-maas --verbose
$ lxc list
+-----------------+---------+-----------------------+---------------------------------------------+-----------------+-----------+
|      NAME       |  STATE  |         IPV4          |                    IPV6                     |      TYPE       | SNAPSHOTS |
+-----------------+---------+-----------------------+---------------------------------------------+-----------------+-----------+
| upward-stallion | RUNNING | 10.196.199.194 (eth0) | fd42:ec:5a53:59d2:216:3eff:febf:7fa7 (eth0) | CONTAINER       | 0         |
+-----------------+---------+-----------------------+---------------------------------------------+-----------------+-----------+
| witty-lizard    | STOPPED |                       |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+-----------------------+---------------------------------------------+-----------------+-----------+
$ lxc project switch not-maas
$ lxc list
+--------------+---------+------+------+-----------------+-----------+
|     NAME     |  STATE  | IPV4 | IPV6 |      TYPE       | SNAPSHOTS |
+--------------+---------+------+------+-----------------+-----------+
| trusty-drake | STOPPED |      |      | VIRTUAL-MACHINE | 0         |
+--------------+---------+------+------+-----------------+-----------+
```

It's important to note that the `move` step may take 30 seconds or more; that's normal.

Next, let's try moving `upward-stallion`, which is a running container:

```nohighlight
$ lxc move upward-stallion upward-stallion --project default --target-project not-maas --verbose
Error: Failed creating instance record: Failed initialising instance: Invalid devices: Failed detecting root disk device: No root device could be found
$ lxc list
+-----------------+---------+-----------------------+---------------------------------------------+-----------------+-----------+
|      NAME       |  STATE  |         IPV4          |                    IPV6                     |      TYPE       | SNAPSHOTS |
+-----------------+---------+-----------------------+---------------------------------------------+-----------------+-----------+
| upward-stallion | RUNNING | 10.196.199.216 (eth0) | fd42:ec:5a53:59d2:216:3eff:fe64:a206 (eth0) | CONTAINER       | 0         |
+-----------------+---------+-----------------------+---------------------------------------------+-----------------+-----------+
| witty-lizard    | STOPPED |                       |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+-----------------------+---------------------------------------------+-----------------+-----------+
```

Hmm, what's that error message about?  Well, you actually need to add the default storage pool to the mix, with this command:

```nohighlight
lxc profile device add default root disk path=/ pool=default
```

Having done so, you can try the move again:

```nohighlight
$ lxc move upward-stallion upward-stallion --project default --target-project not-maas --verbose
$ lxc list                            
+--------------+---------+------+------+-----------------+-----------+
|     NAME     |  STATE  | IPV4 | IPV6 |      TYPE       | SNAPSHOTS |
+--------------+---------+------+------+-----------------+-----------+
| witty-lizard | STOPPED |      |      | VIRTUAL-MACHINE | 0         |
+--------------+---------+------+------+-----------------+-----------+
$ lxc project switch not-maas
$ lxc list
+-----------------+---------+------+------+-----------------+-----------+
|      NAME       |  STATE  | IPV4 | IPV6 |      TYPE       | SNAPSHOTS |
+-----------------+---------+------+------+-----------------+-----------+
| trusty-drake    | STOPPED |      |      | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+------+-----------------+-----------+
| upward-stallion | STOPPED |      |      | CONTAINER       | 0         |
+-----------------+---------+------+------+-----------------+-----------+
```

The move succeeds this time -- with an important distinction: the compartment `upward-stallion` was `STOPPED` by `lxc` during the move. This is an important planning consideration when you're trying to create MAAS VMs and VM hosts in an already-active LXD instantiation.