> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/scripts-and-automation-with-MAAS" target = "_blank">Let us know.</a>*

You can customise your MAAS deployments with scripts:

- [Commissioning Scripts](/t/reference-commissioning-scripts/6605): Control or extend the commissioning process.

- [Hardware Test Scripts](/t/reference-hardware-test-scripts/5392): Add specific tests for your unique hardware configuration.

- [Terraform Integration](/t/reference-terraform/6327): Integrate your IAC practices with MAAS.

### Machine release scripts (MAAS 3.5)

You can also use machine release scripts -- scripts that will be run when releasing a machine from deployment.  These scripts run on an ephemeral copy of Ubuntu that is loaded after the deployed OS has been shut down.  This ephemeral Ubuntu is similar to the OS image used to commission machines.

Release scripts are the same type of scripts that you can create for commissioning or testing, with one difference: `script_type: release`.  Here's a sample release script:

```nohighlight
#!/usr/bin/env python3
#
# hello-maas - Simple release script.
#
# Copyright (C) 2016-2024 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# --- Start MAAS 1.0 script metadata ---
# name: hello-maas
# title: Simple release script
# description: Simple release script
# script_type: release
# packages:
#   apt:
#     - moreutils
# --- End MAAS 1.0 script metadata --

import socket

host = '10.10.10.10'
port = 3333
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((host, port))
s.sendall(b'Hello, MAAS')
s.close()
```

You can upload release scripts via API or CLI with a command similar to this one:

```nohighlight
maas $PROFILE node-scripts create type=release name='hello-maas' script@=/home/ubuntu/hello-maas.py
```

You can check your uploaded release scripts like this:

```nohighlight
maas $PROFILE node-scripts read type=release
```

Among listed scripts you might see one named `wipe-disks`. This is the script that comes with MAAS to support the *Disk Erase* functionality.

Once you have your script uploaded to MAAS, you can pass it as a parameter to the MAAS CLI:

```nohighlight
maas $PROFILE machine release $SYSTEM_ID scripts=hello-maas
```

You can inspect release script results via the MAAS CLI:

```nohighlight
maas $PROFILE node-script-results read $SYSTEM_ID type=release
```