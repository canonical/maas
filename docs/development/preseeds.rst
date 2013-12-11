.. _preseeds:

=========================
How preseeds work in MAAS
=========================

A preseed is what MAAS sends to the ``cloud-init`` process that starts up
as part of node installation and commissioning.  It is a specially formatted
chunk of text.  MAAS does not care what that formatting is, it just knows
it is text and uses Tempita_ templates to render a final file based on
some variables that are required depending on the context.

.. _Tempita: http://pythonpaste.org/tempita/


Preseed template structure
--------------------------

The preseed templates live in the source tree at ``contrib/preseeds_v2/``
and the following files exist there::

  commissioning  enlist_userdata  preseed_master
  enlist         generic          preseed_xinstall

The file that is used as a template for the preseed depends on the state
of the node that is being booted up.

+--------------+----------------------------+
|State         |   Template used            |
+==============+============================+
|Enlistment    |``enlist``                  |
+--------------+----------------------------+
|Commissioning |``commissioning``           |
+--------------+----------------------------+
|Installation  |- ``generic``, plus one of: |
|              |- ``preseed_master`` or     |
|              |- ``preseed_xinstall``      |
+--------------+----------------------------+

The ``enlist_userdata`` is not a preseed but it is a template that's used
to send data to ``cloud-init`` when a new node is enlisted.

There are also `User-provided preseeds`_, see below.


Installation preseed
--------------------

The installation preseed is broken into the three files because the
requirements are different depending on the installer being used.  The
Debian Installer uses ``preseed_master`` and the newer Curtin installer
uses ``preseed_xinstall``.

The base of both of these is ``generic``, which defines some variables
and then selects the right one depending on the installer being used.  Note
that Tempita's inheritance mechanism is a little weird; the ``generic``
template inherits the right file but in effect this is in reverse, the
inherited file becomes the new template and it can then reference the
variables defined in ``generic``.


User-provided preseeds
----------------------

In addition to the standard preseed files, the base preseeds can be
overridden by end users on a per-architecture, OS release and node name basis.
The templates are looked up in the following order::

    {prefix}_{node_architecture}_{node_subarchitecture}_{release}_{node_name}
    {prefix}_{node_architecture}_{node_subarchitecture}_{release}
    {prefix}_{node_architecture}_{node_subarchitecture}
    {prefix}_{node_architecture}
    {prefix}
    'generic'

``prefix`` is either empty or one of ``enlist`` or ``commissioning``.

As you can see this mechanism is also used to calculate the base preseeds for
all of installation, enlistment and commissioning.  It allows end users to
add, for example, a file named ``amd64_generic_saucy`` that would be used
instead of the ``generic`` template at installation time.


Context variables
-----------------

Most of the context variables comes from code in ``src/maasserver/preseed.py``
in the ``get_preseed_context()`` function.  However there are many small
functions in that file, this is the full call tree::

  get_preseed()
    |
    render_preseed()
      |
      load_preseed_template()
      | |
      | get_preseed_filenames()
      | |
      | get_preseed_template()
      |
      get_preseed_context()
      |
      get_node_preseed_context()
      | |
      | compose_preseed() - (comes from src/maasserver/compose_preseed.py)
      |
      template.substitute(**context)
