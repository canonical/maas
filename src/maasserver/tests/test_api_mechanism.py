# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing of the API infrastructure, as opposed to code that uses it to
export API methods.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maastesting.testcase import TestCase
from maasserver.testing.factory import factory

from maasserver.api import (
    api_exported,
    dispatch_methods,
    )


class TestApiExported(TestCase):
    """Testing for the api_exported decorator."""

    def test_invalid_method(self):
        # If the supplied HTTP method is not in the allowed set, it should
        # raise a ValueError.
        random_method = "method" + factory.getRandomString(4)
        decorate = api_exported(random_method)
        self.assertRaises(ValueError, decorate, lambda: None)

    def test_disallowed_methods(self):
        # HTTP methods in dispatch_methods should not be allowed.
        for method in dispatch_methods:
            decorate = api_exported(method=dispatch_methods.get(method))
            self.assertRaises(ValueError, decorate, lambda: None)

    def test_defaulted_names_are_checked_for_validity(self):
        # When not using exported_as, the validity check should apply to
        # the method name too.

        def read():
            # 'read' is prohibited for "GET"
            pass

        decorate = api_exported("GET")
        self.assertRaises(ValueError, decorate, read)

    def test_valid_decoration(self):
        value = "value" + factory.getRandomString()
        decorate = api_exported()
        decorated = decorate(lambda: value)
        self.assertEqual(value, decorated())

    def test_can_pass_export_as(self):
        # Test that passing the optional "export_as" works as expected.
        random_exported_name = "exportedas" + factory.getRandomString()
        decorate = api_exported(
            "POST", exported_as=random_exported_name)
        decorated = decorate(lambda: None)

        self.assertEqual(
            random_exported_name, decorated._api_exported["POST"])

    def test_export_as_is_optional(self):
        # If export_as is not passed then we expect the function to be
        # exported in the API using the actual function name itself.

        def exported_function():
            pass

        decorate = api_exported("POST")
        decorated = decorate(exported_function)

        self.assertEqual("exported_function", decorated._api_exported["POST"])
