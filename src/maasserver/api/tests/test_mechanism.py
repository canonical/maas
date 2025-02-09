# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing of the API infrastructure, as opposed to code that uses it to
export API methods.
"""

from maasserver.api.support import operation
from maasserver.testing.factory import factory
from maastesting.testcase import MAASTestCase


class TestOperationDecorator(MAASTestCase):
    """Testing for the `operation` decorator."""

    def test_valid_decoration(self):
        value = "value" + factory.make_string()
        decorate = operation(idempotent=False)
        decorated = decorate(lambda: value)
        self.assertEqual(value, decorated())

    def test_can_passexported_as(self):
        # Test that passing the optional "exported_as" works as expected.
        randomexported_name = factory.make_name("exportedas", sep="")
        decorate = operation(idempotent=False, exported_as=randomexported_name)
        decorated = decorate(lambda: None)
        self.assertEqual(randomexported_name, decorated.export[1])

    def testexported_as_is_optional(self):
        # If exported_as is not passed then we expect the function to be
        # exported in the API using the actual function name itself.

        def exported_function():
            pass

        decorate = operation(idempotent=True)
        decorated = decorate(exported_function)
        self.assertEqual("exported_function", decorated.export[1])

    def test_idempotent_uses_GET(self):
        # If a function is declared as idempotent the export signature
        # includes the HTTP GET method.
        def func():
            pass

        self.assertEqual(
            ("GET", func.__name__), operation(idempotent=True)(func).export
        )

    def test_non_idempotent_uses_POST(self):
        # If a function is declared as not idempotent the export signature
        # includes the HTTP POST method.
        def func():
            pass

        self.assertEqual(
            ("POST", func.__name__), operation(idempotent=False)(func).export
        )
