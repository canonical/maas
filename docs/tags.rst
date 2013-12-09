.. _deploy-tags:

Making use of Tags
==================

MAAS implements a system of tags based on the physical properties of
the nodes.  The idea behind this is that you can use the tags to
identify nodes with particular abilities which may be useful when it
comes to deploying services.

A real world example of this might be to identify nodes which have
fast GPUs installed, if you were planning on deploying software which
used CUDA or OpenCL which would make use of this hardware.


Tag definitions
---------------

Before we can create a tag we need to know how we will select which nodes it
gets applied to. MAAS collects hardware information from the nodes using the
`"lshw" utility <http://ezix.org/project/wiki/HardwareLiSter>`_ to return
detailed information in XML format. The definitions used in creating a tag are
then constructed using XPath expressions.
If you are unfamiliar with XPath expressions, it is well worth checking out the
`w3schools documentation <http://www.w3schools.com/xpath/xpath_syntax.asp>`_.
For the lshw XML, we will just check all the available nodes for some
properties.
In our example case, we might want to find GPUs with a clock speed of over
1GHz.
In this case, the relevant XML node from the output will be labelled "display"
and does have a property called clock, so it will look like this::

 //node[@id="display"]/clock > 1000000000

Now we have a definition, we can go ahead and create a tag.


Creating a tag
--------------

Once we have sorted out what definition we will be using, creating the
tag is easy using the ``maas-cli`` command. You will need to :ref:`be
logged in to the API first <api-key>`::

  $ maas-cli maas tags new name='gpu' \
    comment='GPU with clock speed >1GHz for running CUDA type operations.' \
    definition='//node[@id="display"]/clock > 1000000000'

The comment is really for your benefit. It pays to keep the actual tag name
short and to the point as you will be using it frequently in commands, but it
may subsequently be hard to work out what exactly was the difference between
tags like "gpu" and "fastgpu" unless you have a good comment. Something which
explains the definition in plain language is always a good idea!

To check which nodes this tag applies to we can use the tag command::

  $ maas-cli maas tag nodes gpu

The process of updating the tags does take some time  - not a lot of time, but
if nothing shows up straight away, try running the command again after a minute
or so.


Using the tag
-------------

You can use the tag in the web interface to discover applicable nodes, but the
real significance of it is when using juju to deploy services. Tags can be used
with juju constraints to make sure that a particular service only gets deployed
on hardware with the tag you have created.

Example:
To use the 'gpu' tag we created to run a service called 'cuda' we would use::

  $ juju deploy --constraints tags=gpu cuda

You could list several tags if required, and mix in other juju constraints if
needed::

  $ juju deploy --constraints "mem=1024 tags=gpu,intel" cuda


Manually assigning tags
-----------------------

MAAS supports the creation of arbitrary tags which don't depend on XPath
definitions ("nodes which make a lot of noise" perhaps). If a tag is created
without specifying the definition parameter then it will simply be ignored by
tag refresh mechanism, but the MAAS administrator will be able to manually add
and remove the tag from specific nodes.

In this example we are assuming you are using the 'maas' profile and you want
to create a tag called 'my_tag'::

  $ maas-cli maas tags new name='my_tag' comment='nodes which go ping'
  $ maas-cli maas tag update-nodes my_tag add="<system_id>"

The first line creates a new tag but omits the definition, so no nodes are
automatically added to it. The second line applies that tag to a specific node
referenced by its system id property.

You can easily remove a tag from a particular node, or indeed add
and remove them at the same time::

  $ maas-cli maas tag update-nodes my_tag add=<system_id_1> \
    add=<system_id_2> add=<system_id_3> remove=<system_id_4>

As the rule is that tags without a definition are ignored when rebuilds are
done, it is also possible to create a normal tag with a definition, and then
subsequently edit it to remove the definition. From this point the tag behaves
as if you had manually created it, but it still retains all the existing
associations it has with nodes. This is particularly useful if you have some
hardware which is conceptually similar but doesn't easily fit within a single
tag definition::

  $ maas-cli maas tag new name='my_tag' comment='nodes I like ' \
     definition='contains(//node[@id=network]/vendor, "Intel")'
  $ maas-cli maas tag update my_tag definition=''
  $ maas-cli mass tag update-nodes my_tag add=<system_id>

.. tip::

   If you add and remove the same node in one operation, it ends up having
   the tag removed (even if the tag was in place before the operation).
