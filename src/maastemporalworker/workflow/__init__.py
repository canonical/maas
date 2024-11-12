#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""
This package contains the workflows and activities definitions.

The workflows interfaces (name, parameters, results) MUST be defined in maascommon.workflows.
The activities interfaces MUST NOT be defined in maascommon. Instead, they should be local to the modules in this package. Each module MUST have the following structure:

# Activities names
...

# Activities parameters
...
"""
