
As well as the web interface, many tasks can be performed by accessing the MAAS API directly through the  maas-cli command. This section details how to login with this tool and perform some common operations.

.. _api-key:

Logging in
----------

Before the API will accept any commands from maas-cli, you must first login. To do this, you need the API key which can be found in the user interface. 

Login to the web interface on your MAAS. Click on the username in the top right corner and select 'Preferences' from the menu which appears.

.. image:: media/maascli-prefs.*

A new page will load... 

.. image:: media/maascli-key.*

The very first item is a list of MAAS keys. One will have already been generated when the system was installed. It's easiest to just select and copy the key (it's quite long!) and then paste it into the commandline::

 $ maas-cli login <key>



