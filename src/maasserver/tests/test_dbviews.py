# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.dbviews`."""

__all__ = []

from contextlib import closing

from django.db import connection
from maasserver.dbviews import (
    _ALL_VIEWS,
    register_all_views,
)
from maasserver.testing.testcase import MAASServerTestCase


class TestDatabaseViews(MAASServerTestCase):

    def test_views_contain_vailid_sql(self):
        # This is a positive test case. The view creation code is very simple,
        # and will just abort with an exception if the SQL is invalid. So all
        # we just need to make sure no execeptions are thrown when the views
        # are created.
        register_all_views()

    def test_each_view_can_be_used(self):
        register_all_views()
        for view_name, view_sql in _ALL_VIEWS:
            with closing(connection.cursor()) as cursor:
                cursor.execute("SELECT * from %s;" % view_name)
