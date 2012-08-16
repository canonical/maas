Juju Quick Start
================

These instructions will help you deploy your first charm with Juju to
a MAAS cluster.

A few assumptions are made:

- You have a MAAS cluster set-up, and you have at least 2 nodes
  enlisted with it.

- You're running MAAS on your local machine. If not you'll need to
  adjust some of the URLs mentioned accordingly.

- You're running Juju from the PPA (``ppa:juju/pkgs``) or from a
  branch of ``lp:juju``. At the time of writing MAAS support had not
  made it into the main Ubuntu archives. However, following the
  release of Ubuntu Precise, all the necessary package revisions will
  be in main.

  If you're using a branch, note that you'll need to set
  ``PYTHONPATH`` carefully to ensure you use the code in the branch.


Your API key, SSH key, and environments.yaml
--------------------------------------------

You'll need an API key from MAAS so that the Juju client can access
it. Each user account in MAAS can have as many API keys as desired.
One hard and fast rule is that you'll need to use a different API key
for each Juju *environment* you set up within a single MAAS cluster.

You'll also need to add an SSH key to MAAS so that you, and Juju, can
SSH into freshly provisioned machines.


Getting a key
^^^^^^^^^^^^^

To get the API key:

#. Go to your `MAAS preferences page`_, or go to your `MAAS home
   page`_ and choose *Preferences* from the drop-down menu that
   appears when clicking your username at the top-right of the page.

#. Optionally add a new MAAS key. Do this if you're setting up another
   environment within the same MAAS cluster.

.. _MAAS preferences page: http://localhost:5240/account/prefs/
.. _MAAS home page: http://localhost:5240/


Adding an SSH key
^^^^^^^^^^^^^^^^^

While you're still on the `MAAS preferences page`_, add your SSH key
by clicking *Add SSH key*. Use the public half of your SSH key, the
content of ``~/.ssh/id_rsa.pub`` for example; don't paste the private
half.


Creating environments.yaml
^^^^^^^^^^^^^^^^^^^^^^^^^^

Create or modify ``~/.juju/environments.yaml`` with the following content::

  juju: environments
  environments:
    maas:
      type: maas
      maas-server: 'http://localhost:5240'
      maas-oauth: '${maas-api-key}'
      admin-secret: 'nothing'

Substitute the API key from earlier into the ``${maas-api-key}``
slot. You may need to modify the ``maas-server`` setting too; if
you're running from the maas package it should be something like
``http://hostname.example.com/MAAS``.


Now Juju
--------

::

  $ juju status

**Note**: if Juju complains that there are multiple environments and
no explicit default, add ``-e ${environment-name}`` after each
command, e.g.::

  $ juju status -e maas

As you've not bootstrapped you ought to see::

  juju environment not found: is the environment bootstrapped?

Bootstrap::

  $ juju bootstrap

This will return quickly, but the master node may take a *long* time
to come up. It has to completely install Ubuntu and Zookeeper and
reboot before it'll be available for use. It's probably worth either
trying a ``juju status`` once in a while to check on progress, or
following the install on the node directly.

  **Beware** of `bug 413415`_ - *console-setup hangs under chroot
  debootstrap with a console login on ttyX* - when monitoring an
  installation on the node.

.. _bug 413415:
  https://bugs.launchpad.net/ubuntu/+source/console-setup/+bug/413415

If you're using ``vdenv`` (included in ``lp:maas``) then ``virsh``
makes it easy to follow on progress::

  $ virsh list
   Id Name                 State
  ----------------------------------
    1 zimmer               running
    2 odev-node02          running

  $ gnome-terminal -e 'virsh console odev-node02' &

..

  ``zimmer`` is the machine on which the MAAS server is running. Here
  ``odev-node02`` is the machine being bootstrapped as the Juju master
  node.

Once the master node has been installed a status command should come
up with something a bit more interesting::

  machines:
    0:
      agent-state: running
      dns-name: odev-node02
      instance-id: /api/1.0/nodes/odev-node02/
      instance-state: unknown
  services: {}

Now it's possible to deploy a charm::

  $ juju deploy --repository /usr/share/doc/juju/examples local:oneiric/mysql
  $ juju status

If you have another node free you can finish off the canonical and by
now familiar example::

  $ juju deploy --repository /usr/share/doc/juju/examples local:oneiric/wordpress
  $ juju add-relation wordpress mysql
  $ juju expose wordpress
  $ juju status

Note that each charm runs on its own host, so each deployment will
actually take as long as it took to bootstrap. Have a beer, drown your
sorrows in liquor, or, my preference, have another cup of tea.

----
