#!/usr/bin/env python2.7
# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Import ephemeral boot images into MAAS cluster controller."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

from provisioningserver.import_images.ephemerals_script import (
    main,
    make_arg_parser,
    )


if __name__ == "__main__":
    parser = make_arg_parser(__doc__)
    args = parser.parse_args()
    main(args)
