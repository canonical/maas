A good understanding of LXD projects is essential for those using LXD VM hosts, especially if you plan to include non-MAAS-controlled VMs in your LXD instance.  Normally, we wouldn't revisit instructions [found elsewhere](https://ubuntu.com/tutorials/introduction-to-lxd-projects#1-overview)**^**, but because the discussion flows quickly and naturally into MAAS-related usage, it seemed prudent to give a light overview of some basic feature information.

## List LXD projects

Before you try to manipulate projects, it's useful to understand how to list them, so that you can check your results as you go.  If you've successfully [installed and initialised lxd](https://linuxcontainers.org/lxd/getting-started-cli/)**^**, you should be able to list projects.  A basic project list can be obtained with the following command:

```nohighlight
lxc project list
``` 

You should get a listing something like this:

```nohighlight
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
|        NAME         | IMAGES | PROFILES | STORAGE VOLUMES | NETWORKS |       DESCRIPTION       | USED BY |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| default (current)   | YES    | YES      | YES             | YES      | Default LXD project     | 7       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| pg-basebackup-tests | NO     | YES      | NO              | NO       | Project managed by MAAS | 16      |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
```

Note that this particular instantiation of LXD has two projects: the default project (which generally always exists in LXD), and a project called `pg-basebackup-tests` which is already managed by MAAS.

There is a column labelled `USED BY`, which tabulates the number of entities contained within the project. There isn't a project-related command to get a list of the containers and VMs within a project.  Instead, you use the LXC command `lxc list`:

```nohighlight
lxc list
```

which yields something like the following tabulated listing:

```nohighlight
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
|      NAME       |  STATE  | IPV4 |                    IPV6                     |      TYPE       | SNAPSHOTS |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| trusty-drake    | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| upward-stallion | RUNNING |      | fd42:ec:5a53:59d2:216:3eff:febf:7fa7 (eth0) | CONTAINER       | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| witty-lizard    | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| crazy-goose     | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| dirty-horse     | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| confused-mouse  | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| uplifting-dog   | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
```

How do you know which project you're listing?  The most reliable way is to first list projects and see which one is marked `(current)`, like this:

```nohighlight
lxc project list
```

As you see in the sample output, the currently visible and accessible project is listed as `(current)` in the project listing:

```nohighlight
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
|        NAME         | IMAGES | PROFILES | STORAGE VOLUMES | NETWORKS |       DESCRIPTION       | USED BY |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| default (current)   | YES    | YES      | YES             | YES      | Default LXD project     | 7       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| pg-basebackup-tests | NO     | YES      | NO              | NO       | Project managed by MAAS | 16      |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
```

We'll show you how to switch to a different project further along in this tutorial.

## Create LXD project

Suppose that you're about to create a MAAS VM host, and you want a specific project named "maas-vm-host-1" for this particular situation.  You can create that project with the following command:

```nohighlight
$ lxc project create maas-vm-host-1
Project maas-vm-host-1 created
```

When you check your work with `lxc project list`, you'll see that LXD did not automatically switch to the new project:

```nohighlight
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
|        NAME         | IMAGES | PROFILES | STORAGE VOLUMES | NETWORKS |       DESCRIPTION       | USED BY |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| default (current)   | YES    | YES      | YES             | YES      | Default LXD project     | 7       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| maas-vm-host-1      | YES    | YES      | YES             | NO       |                         | 1       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| pg-basebackup-tests | NO     | YES      | NO              | NO       | Project managed by MAAS | 16      |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
```

The `lxc` tool generally does only what you ask, nothing more.  

## Delete LXD project

Now, suppose that you decide you don't need this project yet.  No worries: you can easily delete it like this:

```nohighlight
$ lxc project delete maas-vm-host-1
Project maas-vm-host-1 deleted
```

You can check that it was successfully deleted with the `lxc project list` command:

```nohighlight
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
|        NAME         | IMAGES | PROFILES | STORAGE VOLUMES | NETWORKS |       DESCRIPTION       | USED BY |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| default (current)   | YES    | YES      | YES             | YES      | Default LXD project     | 7       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| pg-basebackup-tests | NO     | YES      | NO              | NO       | Project managed by MAAS | 16      |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
```

## Rename LXD project

On the other hand, maybe you didn't need to actually delete that project, just change the name to `maas-vm-host-001`, which is what you really wanted in the first place.  Consider your original project name, `maas-vm-host-1`:

```nohighlight
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
|        NAME         | IMAGES | PROFILES | STORAGE VOLUMES | NETWORKS |       DESCRIPTION       | USED BY |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| default (current)   | YES    | YES      | YES             | YES      | Default LXD project     | 7       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| maas-vm-host-1      | YES    | YES      | YES             | NO       |                         | 1       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| pg-basebackup-tests | NO     | YES      | NO              | NO       | Project managed by MAAS | 16      |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
```

You can quickly and easily change the project name like this:

```nohighlight
$ lxc project rename maas-vm-host-1 maas-vm-host-001
Project maas-vm-host-1 renamed to maas-vm-host-001
$ lxc project list
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
|        NAME         | IMAGES | PROFILES | STORAGE VOLUMES | NETWORKS |       DESCRIPTION       | USED BY |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| default (current)   | YES    | YES      | YES             | YES      | Default LXD project     | 7       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| maas-vm-host-001    | YES    | YES      | YES             | NO       |                         | 1       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| pg-basebackup-tests | NO     | YES      | NO              | NO       | Project managed by MAAS | 16      |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
```

From now on, we'll be combining command output with the command invocation, most of the time.

## Switch between LXD projects

You can choose which LXD project is currently visible and accessible, that is, you can choose which project will be acted on by most of the other project commands.  Let's begin by listing the current projects:

```nohighlight
$ lxc project list
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
|        NAME         | IMAGES | PROFILES | STORAGE VOLUMES | NETWORKS |       DESCRIPTION       | USED BY |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| default (current)   | YES    | YES      | YES             | YES      | Default LXD project     | 7       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| maas-vm-host-001    | YES    | YES      | YES             | NO       |                         | 1       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| pg-basebackup-tests | NO     | YES      | NO              | NO       | Project managed by MAAS | 16      |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
```

Only the project marked `(current)` in the project listing can be manipulated, for the most part, with the obvious exceptions of command that take project names (like "create," "delete," and so forth).  For example, using `lxc list` to enumerate the names of containers and VMs limits its scope to the current project, which is till "default" at this point:

```nohighlight
$ lxc list
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
|      NAME       |  STATE  | IPV4 |                    IPV6                     |      TYPE       | SNAPSHOTS |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| trusty-drake    | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| upward-stallion | RUNNING |      | fd42:ec:5a53:59d2:216:3eff:febf:7fa7 (eth0) | CONTAINER       | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| witty-lizard    | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| crazy-goose     | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| dirty-horse     | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| confused-mouse  | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| uplifting-dog   | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
```

Suppose I want to know what all those "USE BY" things are in that `pg-basebackup-tests` project?  Well, the most straightforward way to get that list is to first switch projects, like this:

```nohighlight
lxc project switch pg-basebackup-tests
```

This command returns nothing if successful (following the old UNIX rule of "no news is good news").  If you now repeat the project list command, like this:

```nohighlight
$ lxc project list
+-------------------------------+--------+----------+-----------------+----------+-------------------------+---------+
|             NAME              | IMAGES | PROFILES | STORAGE VOLUMES | NETWORKS |       DESCRIPTION       | USED BY |
+-------------------------------+--------+----------+-----------------+----------+-------------------------+---------+
| default                       | YES    | YES      | YES             | YES      | Default LXD project     | 7       |
+-------------------------------+--------+----------+-----------------+----------+-------------------------+---------+
| maas-vm-host-001              | YES    | YES      | YES             | NO       |                         | 1       |
+-------------------------------+--------+----------+-----------------+----------+-------------------------+---------+
| pg-basebackup-tests (current) | NO     | YES      | NO              | NO       | Project managed by MAAS | 16      |
+-------------------------------+--------+----------+-----------------+----------+-------------------------+---------+
```

You can see in the above listing that we've switched to the "...-tests" project.  Now when we do a container list, we'll see a different set:

```nohighlight
$ lxc list
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
|      NAME       |  STATE  | IPV4 |                    IPV6                     |      TYPE       | SNAPSHOTS |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| whacky-moose    | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| peeved-gerbil   | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| hairy-nutria    | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| mad-crocodile   | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| flirty-possum   | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| angry-armadillo | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| sneaky-snake    | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| happy-catfish   | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| cute-kitten     | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| bombastic-dog   | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| articulate-eel  | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| morbid-owl      | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| drunk-crow      | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| spicy-alligator | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
| nice-crawfish   | STOPPED |      |                                             | VIRTUAL-MACHINE | 0         |
+-----------------+---------+------+---------------------------------------------+-----------------+-----------+
```

It's good practice to always switch projects carefully, so you're not operating in some other project and creating chaos by accident.

## View LXD project resources

We said that `lxc` commands operate on the current project most of the time.  We gave that caveat because of commands like `lxc project info`, which requires a project name to get any usable output.  For example, if you just type `lxc project info`, you'll just get some "help" output:

```nohighlight
$ lxc project info
Description:
  Get a summary of resource allocations

Usage:
  lxc project info [<remote>:]<project> <key> [flags]

Flags:
      --format   Format (csv|json|table|yaml) (default "table")

Global Flags:
      --debug            Show all debug messages
      --force-local      Force using the local unix socket
  -h, --help             Print help
      --project string   Override the source project
  -q, --quiet            Don't show progress information
  -v, --verbose          Show all information messages
      --version          Print version number
```

You can see from the help listing that a project name is required.  Let's try that again with a fairly large project:

```nohighlight
$ lxc project info pg-basebackup-tests
+------------------+-----------+----------+
|     RESOURCE     |   LIMIT   |  USAGE   |
+------------------+-----------+----------+
| CONTAINERS       | UNLIMITED | 0        |
+------------------+-----------+----------+
| CPU              | UNLIMITED | 15       |
+------------------+-----------+----------+
| DISK             | UNLIMITED | 120.00GB |
+------------------+-----------+----------+
| INSTANCES        | UNLIMITED | 15       |
+------------------+-----------+----------+
| MEMORY           | UNLIMITED | 32.21GB  |
+------------------+-----------+----------+
| NETWORKS         | UNLIMITED | 0        |
+------------------+-----------+----------+
| PROCESSES        | UNLIMITED | 0        |
+------------------+-----------+----------+
| VIRTUAL-MACHINES | UNLIMITED | 15       |
+------------------+-----------+----------+
```

Here we see that the `pg-basebackup-tests` file has no containers, 15 VMs, 120GB of disk space used, etc.  You can do this for any project, even if it's not the current project, so from where we are here (in the `pg-basebackup-tests` project), we can still check resources in the `default` project:

```nohighlight
$ lxc project info default
+------------------+-----------+---------+
|     RESOURCE     |   LIMIT   |  USAGE  |
+------------------+-----------+---------+
| CONTAINERS       | UNLIMITED | 1       |
+------------------+-----------+---------+
| CPU              | UNLIMITED | 2       |
+------------------+-----------+---------+
| DISK             | UNLIMITED | 16.00GB |
+------------------+-----------+---------+
| INSTANCES        | UNLIMITED | 3       |
+------------------+-----------+---------+
| MEMORY           | UNLIMITED | 4.29GB  |
+------------------+-----------+---------+
| NETWORKS         | UNLIMITED | 2       |
+------------------+-----------+---------+
| PROCESSES        | UNLIMITED | 0       |
+------------------+-----------+---------+
| VIRTUAL-MACHINES | UNLIMITED | 2       |
+------------------+-----------+---------+
```

Note that `lxc project info` requires a project name.  As mentioned earlier, typing the command without a project name just gives you a help message, not the stats for the default or current projects.

## Show LXD project options

You'll remember that the "USED BY" column seemed to list more entities than there were containers or VMs.  For example, the `default` project is "USED BY" seven entities, but only shows three containers or VMs:

```nohighlight
$ lxc project list
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
|        NAME         | IMAGES | PROFILES | STORAGE VOLUMES | NETWORKS |       DESCRIPTION       | USED BY |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| default (current)   | YES    | YES      | YES             | YES      | Default LXD project     | 7       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| maas-vm-host-001    | YES    | YES      | YES             | NO       |                         | 1       |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
| pg-basebackup-tests | NO     | YES      | NO              | NO       | Project managed by MAAS | 16      |
+---------------------+--------+----------+-----------------+----------+-------------------------+---------+
```

You can make more sense of the "USED BY" column, and get a lot more information about your project, by using the `lxc project show` command:

```nohighlight
$ lxc project show default
config:
  features.images: "true"
  features.networks: "true"
  features.profiles: "true"
  features.storage.volumes: "true"
description: Default LXD project
name: default
used_by:
- /1.0/images/9a30ffb2faeea61cce6012c63071a1f1504a76e1dbbe03e575cc313170fdaf43
- /1.0/instances/trusty-drake
- /1.0/instances/upward-stallion
- /1.0/instances/witty-lizard
- /1.0/networks/lxdbr0
- /1.0/networks/lxdbr1
- /1.0/profiles/default
```

Here you'll see several categories of information, notably as list of entities that are using this project.  For example, there are three VMs/containers, two networks, one image, and the default profile.

What's really interesting, though, is that the `pg-basebackup-tests` project is only used by 16 entities -- but there are 15 VMs in that project.  What's that discrepancy about?  Well, we can find out by showing the options for that project:

```nohighlight
$ lxc project show pg-basebackup-tests
config:
  features.images: "false"
  features.profiles: "true"
  features.storage.volumes: "false"
description: Project managed by MAAS
name: pg-basebackup-tests
used_by:
- /1.0/instances/whacky-moose?project=pg-basebackup-tests
- /1.0/instances/peeved-gerbil?project=pg-basebackup-tests
- /1.0/instances/hairy-nutria?project=pg-basebackup-tests
- /1.0/instances/mad-crocodile?project=pg-basebackup-tests
- /1.0/instances/flirty-possum?project=pg-basebackup-tests
- /1.0/instances/angry-armadillo?project=pg-basebackup-tests
- /1.0/instances/sneaky-snake?project=pg-basebackup-tests
- /1.0/instances/happy-catfish?project=pg-basebackup-tests
- /1.0/instances/cute-kitten?project=pg-basebackup-tests
- /1.0/instances/bombastic-dog?project=pg-basebackup-tests
- /1.0/instances/articulate-eel?project=pg-basebackup-tests
- /1.0/instances/morbid-owl?project=pg-basebackup-tests
- /1.0/instances/drunk-crow?project=pg-basebackup-tests
- /1.0/instances/spicy-alligator?project=pg-basebackup-tests
- /1.0/instances/nice-crawfish?project=pg-basebackup-tests
- /1.0/profiles/default?project=pg-basebackup-tests
```

Here you can see that the non-default project contains only a default profile for itself, and the 15 VMs added there.  The other entities aren't needed here, or can be accessed in the	`default` project if required.