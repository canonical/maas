# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test ORM utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from itertools import repeat

from django.core.exceptions import MultipleObjectsReturned
from django.db import (
    connection,
    transaction,
    )
from django.db.transaction import TransactionManagementError
from django.db.utils import OperationalError
from maasserver.fields import MAC
from maasserver.testing.testcase import SerializationFailureTestCase
from maasserver.utils import orm
from maasserver.utils.orm import (
    commit_within_atomic_block,
    get_first,
    get_one,
    is_serialization_failure,
    macs_contain,
    macs_do_not_contain,
    make_serialization_failure,
    outside_atomic_block,
    psql_array,
    request_transaction_retry,
    retry_on_serialization_failure,
    validate_in_transaction,
    )
from maastesting.djangotestcase import TransactionTestCase
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    call,
    Mock,
    sentinel,
    )
from psycopg2.errorcodes import SERIALIZATION_FAILURE
from testtools.matchers import MatchesPredicate


class FakeModel:

    class MultipleObjectsReturned(MultipleObjectsReturned):
        pass

    def __init__(self, name):
        self.name == name

    def __repr__(self):
        return self.name


class FakeQueryResult:
    """Something that looks, to `get_one`, close enough to a Django model."""

    def __init__(self, model, items):
        self.model = model
        self.items = items

    def __iter__(self):
        return self.items.__iter__()

    def __repr__(self):
        return "<FakeQueryResult: %r>" % self.items


class TestGetOne(MAASTestCase):

    def test_get_one_returns_None_for_empty_list(self):
        self.assertIsNone(get_one([]))

    def test_get_one_returns_single_list_item(self):
        item = factory.make_string()
        self.assertEqual(item, get_one([item]))

    def test_get_one_returns_None_from_any_empty_sequence(self):
        self.assertIsNone(get_one("no item" for counter in range(0)))

    def test_get_one_returns_item_from_any_sequence_of_length_one(self):
        item = factory.make_string()
        self.assertEqual(item, get_one(item for counter in range(1)))

    def test_get_one_does_not_trigger_database_counting(self):
        # Avoid typical performance pitfall of querying objects *and*
        # the number of objects.
        item = factory.make_string()
        sequence = FakeQueryResult(type(item), [item])
        sequence.__len__ = Mock(side_effect=Exception("len() was called"))
        self.assertEqual(item, get_one(sequence))

    def test_get_one_does_not_iterate_long_sequence_indefinitely(self):
        # Avoid typical performance pitfall of retrieving all objects.
        # In rare failure cases, there may be large numbers.  Fail fast.

        class InfinityException(Exception):
            """Iteration went on indefinitely."""

        def infinite_sequence():
            """Generator: count to infinity (more or less), then fail."""
            for counter in range(3):
                yield counter
            raise InfinityException()

        # Raises MultipleObjectsReturned as spec'ed.  It does not
        # iterate to infinity first!
        self.assertRaises(
            MultipleObjectsReturned, get_one, infinite_sequence())

    def test_get_one_raises_model_error_if_query_result_is_too_big(self):
        self.assertRaises(
            FakeModel.MultipleObjectsReturned,
            get_one,
            FakeQueryResult(FakeModel, range(2)))

    def test_get_one_raises_generic_error_if_other_sequence_is_too_big(self):
        self.assertRaises(MultipleObjectsReturned, get_one, range(2))


class TestGetFirst(MAASTestCase):
    def test_get_first_returns_None_for_empty_list(self):
        self.assertIsNone(get_first([]))

    def test_get_first_returns_first_item(self):
        items = [factory.make_string() for counter in range(10)]
        self.assertEqual(items[0], get_first(items))

    def test_get_first_accepts_any_sequence(self):
        item = factory.make_string()
        self.assertEqual(item, get_first(repeat(item)))

    def test_get_first_does_not_retrieve_beyond_first_item(self):

        class SecondItemRetrieved(Exception):
            """Second item as retrieved.  It shouldn't be."""

        def multiple_items():
            yield "Item 1"
            raise SecondItemRetrieved()

        self.assertEqual("Item 1", get_first(multiple_items()))


class TestGetPredicateUtilities(MAASTestCase):

    def test_macs_contain_returns_predicate(self):
        macs = ['11:22:33:44:55:66', 'aa:bb:cc:dd:ee:ff']
        where, params = macs_contain('key', macs)
        self.assertEqual(
            (where, params),
            ('key @> ARRAY[%s, %s]::macaddr[]', macs))

    def test_macs_contain_returns_predicate_using_MACs(self):
        macs = [MAC('11:22:33:44:55:66')]
        where, params = macs_contain('key', macs)
        self.assertEqual(
            (where, params),
            ('key @> ARRAY[%s]::macaddr[]', macs))

    def test_macs_do_not_contain_returns_predicate(self):
        macs = ['11:22:33:44:55:66', 'aa:bb:cc:dd:ee:ff']
        where, params = macs_do_not_contain('key', macs)
        self.assertEqual(
            (where, params),
            (
                (
                    '((key IS NULL) OR NOT '
                    '(key @> ARRAY[%s]::macaddr[] OR '
                    'key @> ARRAY[%s]::macaddr[]))'
                ),
                macs,
            ))


class TestSerializationFailure(SerializationFailureTestCase):
    """Detecting SERIALIZABLE isolation failures."""

    def test_serialization_failure_detectable_via_error_cause(self):
        error = self.assertRaises(
            OperationalError, self.cause_serialization_failure)
        self.assertEqual(
            SERIALIZATION_FAILURE, error.__cause__.pgcode)


class TestIsSerializationFailure(SerializationFailureTestCase):
    """Tests relating to MAAS's use of SERIALIZABLE isolation."""

    def test_detects_operational_error_with_matching_cause(self):
        error = self.assertRaises(
            OperationalError, self.cause_serialization_failure)
        self.assertTrue(is_serialization_failure(error))

    def test_rejects_operational_error_without_matching_cause(self):
        error = OperationalError()
        cause = self.patch(error, "__cause__")
        cause.pgcode = factory.make_name("pgcode")
        self.assertFalse(is_serialization_failure(error))

    def test_rejects_operational_error_with_unrelated_cause(self):
        error = OperationalError()
        error.__cause__ = object()
        self.assertFalse(is_serialization_failure(error))

    def test_rejects_operational_error_without_cause(self):
        error = OperationalError()
        self.assertFalse(is_serialization_failure(error))

    def test_rejects_non_operational_error_with_matching_cause(self):
        error = factory.make_exception()
        cause = self.patch(error, "__cause__")
        cause.pgcode = SERIALIZATION_FAILURE
        self.assertFalse(is_serialization_failure(error))


class TestRetryOnSerializationFailure(SerializationFailureTestCase):

    def make_mock_function(self):
        function_name = factory.make_name("function")
        function = Mock(__name__=function_name.encode("ascii"))
        return function

    def test_retries_twice_on_serialization_failure(self):
        function = self.make_mock_function()
        function.side_effect = self.cause_serialization_failure
        function_wrapped = retry_on_serialization_failure(function)
        self.assertRaises(OperationalError, function_wrapped)
        expected_calls = [call()] * 10
        self.assertThat(function, MockCallsMatch(*expected_calls))

    def test_retries_on_serialization_failure_until_successful(self):
        serialization_error = self.assertRaises(
            OperationalError, self.cause_serialization_failure)
        function = self.make_mock_function()
        function.side_effect = [serialization_error, sentinel.result]
        function_wrapped = retry_on_serialization_failure(function)
        self.assertEqual(sentinel.result, function_wrapped())
        self.assertThat(function, MockCallsMatch(call(), call()))

    def test_passes_args_to_wrapped_function(self):
        function = lambda a, b: (a, b)
        function_wrapped = retry_on_serialization_failure(function)
        self.assertEqual(
            (sentinel.a, sentinel.b),
            function_wrapped(sentinel.a, b=sentinel.b))


class TestMakeSerializationFailure(MAASTestCase):
    """Tests for `make_serialization_failure`."""

    def test__makes_a_serialization_failure(self):
        exception = make_serialization_failure()
        self.assertThat(exception, MatchesPredicate(
            is_serialization_failure, "%r is not a serialization failure."))


class TestRequestTransactionRetry(MAASTestCase):
    """Tests for `request_transaction_retry`."""

    def test__raises_a_serialization_failure(self):
        exception = self.assertRaises(
            OperationalError, request_transaction_retry)
        self.assertThat(exception, MatchesPredicate(
            is_serialization_failure, "%r is not a serialization failure."))


class TestOutsideAtomicBlock(MAASTestCase):
    """Tests for `outside_atomic_block`."""

    def test__leaves_and_restores_atomic_block(self):
        self.assertFalse(connection.in_atomic_block)
        with transaction.atomic():
            self.assertTrue(connection.in_atomic_block)
            with outside_atomic_block():
                self.assertFalse(connection.in_atomic_block)
            self.assertTrue(connection.in_atomic_block)
        self.assertFalse(connection.in_atomic_block)

    def test__leaves_and_restores_multiple_levels_of_atomic_blocks(self):
        self.assertFalse(connection.in_atomic_block)
        with transaction.atomic():
            with transaction.atomic():
                with transaction.atomic():
                    with transaction.atomic():
                        with outside_atomic_block():
                            # It leaves the multiple levels of atomic blocks,
                            # but puts the same number of levels back in place
                            # on exit.
                            self.assertFalse(connection.in_atomic_block)
                        self.assertTrue(connection.in_atomic_block)
                    self.assertTrue(connection.in_atomic_block)
                self.assertTrue(connection.in_atomic_block)
            self.assertTrue(connection.in_atomic_block)
        self.assertFalse(connection.in_atomic_block)

    def test__restores_atomic_block_even_on_error(self):
        with transaction.atomic():
            exception_type = factory.make_exception_type()
            try:
                with outside_atomic_block():
                    raise exception_type()
            except exception_type:
                self.assertTrue(connection.in_atomic_block)


class TestCommitWithinAtomicBlock(MAASTestCase):
    """Tests for `commit_within_atomic_block`."""

    def test__relies_on_outside_atomic_block(self):
        outside_atomic_block = self.patch(orm, "outside_atomic_block")
        with transaction.atomic():
            commit_within_atomic_block()
        self.expectThat(outside_atomic_block, MockCalledOnceWith("default"))
        context_manager = outside_atomic_block.return_value
        self.expectThat(
            context_manager.__enter__, MockCalledOnceWith())
        self.expectThat(
            context_manager.__exit__, MockCalledOnceWith(None, None, None))


class TestValidateInTransaction(TransactionTestCase):
    """Tests for `validate_in_transaction`."""

    def test__does_nothing_within_atomic_block(self):
        with transaction.atomic():
            validate_in_transaction(connection)

    def test__does_nothing_when_legacy_transaction_is_active(self):
        transaction.enter_transaction_management()
        try:
            validate_in_transaction(connection)
        finally:
            transaction.leave_transaction_management()

    def test__explodes_when_no_transaction_is_active(self):
        self.assertRaises(
            TransactionManagementError,
            validate_in_transaction, connection)


class TestPsqlArray(MAASTestCase):

    def test__returns_empty_array(self):
        self.assertEqual(("ARRAY[]", []), psql_array([]))

    def test__returns_params_in_array(self):
        self.assertEqual(
            "ARRAY[%s,%s,%s]", psql_array(['a', 'a', 'a'])[0])

    def test__returns_params_in_tuple(self):
        params = [factory.make_name('param') for _ in range(3)]
        self.assertEqual(
            params, psql_array(params)[1])

    def test__returns_cast_to_type(self):
        self.assertEqual(
            ("ARRAY[]::integer[]", []), psql_array([], sql_type="integer"))
