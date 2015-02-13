.. _preseeds:

=========================
How preseeds work in MAAS
=========================

A preseed is what MAAS sends to the ``cloud-init`` process that starts up
as part of node enlistment, commissioning and installation.  It is a
specially formatted chunk of text.  MAAS does not care what that formatting
is, it just knows it is text and uses Tempita_ templates to render a final
file based on variables that are required depending on the context.

.. _Tempita: http://pythonpaste.org/tempita/


Preseed templates
-----------------

On a live system, the preseed templates live in ``/etc/maas/preseeds/``.

Each template uses a prefix that corresponds to a particular "phase":

+---------------+--------------------------+
| Phase         | Prefix used              |
+===============+==========================+
| Enlistment    | enlist                   |
+---------------+--------------------------+
| Commissioning | commissioning            |
+---------------+--------------------------+
| Installation  | preseed_master (DI_) or  |
|               | curtin (Curtin_)         |
+---------------+--------------------------+

.. _DI: https://www.debian.org/devel/debian-installer/

.. _Curtin: https://launchpad.net/curtin

Note that the preseed information is in fact composed of two files: the
preseed file per se which usually contains little more than a URL and the
credentials where to get the "user data" which, in turn, contains most of
the logic to be executed.

Installation preseed
--------------------

The installation preseed is broken into the three files because the
requirements are different depending on the installer being used.  The
`Debian Installer`_ uses ``preseed_master`` and the newer Curtin_ installer
uses ``curtin_userdata``.

.. _Debian Installer: https://www.debian.org/devel/debian-installer/

.. _Curtin: https://launchpad.net/curtin

The base of both of these is ``generic``, which defines some variables
and then selects the right one depending on the installer being used.  Note
that Tempita's inheritance mechanism is a little weird; the ``generic``
template inherits the right file but in effect this is in reverse, the
inherited file becomes the new template and it can then reference the
variables defined in ``generic``.


User-provided preseeds
----------------------

In addition to the standard preseed files, the base preseeds can be
overridden on a per-OS, architecture, subarchitecture, OS release and
node name basis. The templates are looked up in the following order::

    {prefix}_{osystem}_{node_arch}_{node_subarch}_{release}_{node_name}
    {prefix}_{osystem}_{node_arch}_{node_subarch}_{release}
    {prefix}_{osystem}_{node_arch}_{node_subarch}
    {prefix}_{osystem}_{node_arch}
    {prefix}_{osystem}
    {prefix}
    'generic'

``prefix`` is either empty or one of ``enlist``, ``enlist_userdata``,
``commissioning``, ``curtin``, ``curtin_userdata`` or ``preseed_master``.

As you can see this mechanism is also used to calculate the base preseeds for
all of installation, enlistment and commissioning.  It allows end users to
add, for example, a file named ``curtin_ubuntu_amd64_generic`` that would be
used at installation time.


Curtin configuration
--------------------

Curtin_ is the tool responsible for performing the OS installation.  If you
need to customize the installation, you need to change Curtin's user data
(by either changing the existing ``curtin_userdata`` file or adding a custom
version as described above).

.. _Curtin: https://launchpad.net/curtin

There isn't a complete documentation on how to customize Curtin at the time of
this writing but the following instructions and examples should cover most of
the use cases.

Curtin provides hooks to execute custom code before (`early`) or after (`late`)
the installation takes place.  You can override these hooks to execute code,
either code that will run in the ephemeral environment or in the machine being
installed itself (`in-target`).  Note that you can execute `in-target` code
only in a `late` command.

Example: early command
======================

Here is an example of an early command (i.e. one that will run before the
installation takes place) that runs in the ephemeral environment and
pings an external machine to signal that the installation is about to start.

.. code:: yaml

  early_commands:
    signal: [wget, '--no-proxy', 'http://example.com/', '--post-data', 'system_id={{node.system_id}}&signal=starting_install', '-O', '/dev/null']

Example: late command
======================

Here is an example of two late commands (i.e. commands that will run after the
installation has been performed).  Both run `in-target` (i.e. in the machine
being installed).  The first command adds a PPA to the machine.  The second
command create a file containing the node's system_id.  (Note that these are
just examples of the things that can be done.)

.. code:: yaml

  late_commands:
    add_repo: ["curtin", "in-target", "--", "add-apt-repository", "-y", "ppa:my/ppa"]
    custom: curtin in-target -- sh -c "/bin/echo -en 'Installed {{node.system_id}}' > /tmp/maas_system_id"
