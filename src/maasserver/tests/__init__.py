# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from os.path import dirname

from django.utils.unittest import defaultTestLoader


def suite():
    return defaultTestLoader.discover(dirname(__file__))
