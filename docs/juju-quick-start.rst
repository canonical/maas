Juju Quick Start
================

These instructions will help you deploy your first charm with Juju to
a MAAS cluster.

In the following, we assume that you have a MAAS cluster set-up with at least
2 nodes enlisted with it.


Your API key, SSH key, and environments.yaml
--------------------------------------------

You'll need an API key from MAAS so that the Juju client can access
it. Each user account in MAAS can have as many API keys as desired.
One hard and fast rule is that you'll need to use a different API key
for each Juju *environment* you set up within a single MAAS cluster.

There is no need to explicitly add an SSH key to MAAS when using Juju;
it will automatically put your public key on any hosts that it starts up.

**Note**: You do not need to use the MAAS web UI or API to allocate
a node to yourself, Juju will do this for you.


Getting a key
^^^^^^^^^^^^^

To get the API key:

#. Go to your MAAS preferences page (go to your MAAS home page
   ``http://${my-maas-server}:80/MAAS/`` and choose *Preferences* from the
   drop-down menu that appears when clicking your username at the top-right
   of the page).

#. Optionally add a new MAAS key. Do this if you're setting up another
   environment within the same MAAS cluster.

The ``${my-maas-server}`` slot should be replaced with the hostname of your
MAAS server.


Adding an SSH key
^^^^^^^^^^^^^^^^^

While you're still on the MAAS preferences page, add your SSH key
by clicking *Add SSH key*. Use the public half of your SSH key, the
content of ``~/.ssh/id_rsa.pub`` for example; don't paste the private
half.


Creating environments.yaml
^^^^^^^^^^^^^^^^^^^^^^^^^^

Create or modify ``~/.juju/environments.yaml`` with the following content::

  environments:
    maas:
      type: maas
      maas-server: 'http://${my-maas-server}:80/MAAS'
      maas-oauth: '${maas-api-key}'
      admin-secret: ${your-admin-secret}
      default-series: precise

Substitute the API key from earlier into the ``${maas-api-key}``
slot, and the hostname of your MAAS server into the ``${my-maas-server}``
slot.

The ``${your-admin-secret}`` slot should be replaced with a random pass-phrase,
there is no default.


Now Juju
--------

If juju-core is not yet installed on the client machine, run::

  $ sudo apt-get install juju-core

Now, use juju to display the status of the default environment::

  $ juju status

As you've not bootstrapped you ought to see::

  error: Unable to connect to environment "".
  Please check your credentials or use 'juju bootstrap' to create a new environment.

**Note**: if Juju complains that there are multiple environments and
no explicit default, add ``-e ${environment-name}`` after each
command, e.g.::

  $ juju status -e maas

Bootstrap::

  $ juju --sync-tools
  $ juju bootstrap

If bootstrapping on a version of juju older than 1.14.0 then use::

  $ juju bootstrap --upload-tools

This will return quickly, but the master node may take a *long* time
to come up. It has to completely install Ubuntu and Juju on it and
reboot before it'll be available for use. It's probably worth either
trying a ``juju status`` once in a while to check on progress, or
following the install on the node directly.

  **Beware** of `bug 413415`_ - *console-setup hangs under chroot
  debootstrap with a console login on ttyX* - when monitoring an
  installation on the node.

.. _bug 413415:
  https://bugs.launchpad.net/ubuntu/+source/console-setup/+bug/413415

Once the boostrap node has been installed a status command should
come up with something a bit more interesting::

  environment: maas
  machines:
    "0":
      agent-state: started
      agent-version: 1.13.3.1
      dns-name: kmhwd.master
      instance-id: /MAAS/api/1.0/nodes/node-5c5b713a-1afc-11e3-9904-525400123456/
      series: precise
  services: {}

Now it's possible to deploy a charm::

  $ juju deploy mysql
  $ juju status

If you have another node free you can finish off the canonical and by
now familiar example::

  $ juju deploy wordpress
  $ juju add-relation wordpress mysql
  $ juju expose wordpress
  $ juju status

Note that each charm runs on its own host, so each deployment will
actually take as long as it took to bootstrap. Have a beer, drown your
sorrows in liquor, or, my preference, have another cup of tea.
