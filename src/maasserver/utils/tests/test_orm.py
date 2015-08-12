# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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

from itertools import (
    islice,
    repeat,
)
from random import randint
import time

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
    get_psycopg2_exception,
    get_psycopg2_serialization_exception,
    is_serialization_failure,
    macs_contain,
    macs_do_not_contain,
    make_serialization_failure,
    outside_atomic_block,
    post_commit,
    post_commit_do,
    post_commit_hooks,
    psql_array,
    request_transaction_retry,
    retry_on_serialization_failure,
    savepoint,
    validate_in_transaction,
)
from maastesting.djangotestcase import DjangoTransactionTestCase
from maastesting.factory import factory
from maastesting.matchers import (
    HasLength,
    IsFiredDeferred,
    LessThanOrEqual,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    call,
    Mock,
    sentinel,
)
from provisioningserver.utils.twisted import (
    callOut,
    DeferredValue,
)
import psycopg2
from psycopg2.errorcodes import SERIALIZATION_FAILURE
from testtools import ExpectedException
from testtools.deferredruntest import extract_result
from testtools.matchers import (
    AllMatch,
    Equals,
    Is,
    IsInstance,
    MatchesPredicate,
    Not,
)
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    passthru,
)
from twisted.python.failure import Failure


def setUp():
    # Prevent real sleeps.
    orm.sleep = lambda _: None


def tearDown():
    # Re-enable real sleeps.
    orm.sleep = time.sleep


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


class TestGetPsycopg2Exception(MAASTestCase):
    """Tests for `get_psycopg2_exception`."""

    def test__returns_psycopg2_error(self):
        exception = psycopg2.Error()
        self.assertIs(exception, get_psycopg2_exception(exception))

    def test__returns_None_for_other_error(self):
        exception = factory.make_exception()
        self.assertIsNone(get_psycopg2_serialization_exception(exception))

    def test__returns_psycopg2_error_root_cause(self):
        exception = Exception()
        exception.__cause__ = orm.SerializationFailure()
        self.assertIs(exception.__cause__, get_psycopg2_exception(exception))


class TestGetPsycopg2SerializationException(MAASTestCase):
    """Tests for `get_psycopg2_serialization_exception`."""

    def test__returns_None_for_plain_psycopg2_error(self):
        exception = psycopg2.Error()
        self.assertIsNone(get_psycopg2_serialization_exception(exception))

    def test__returns_None_for_other_error(self):
        exception = factory.make_exception()
        self.assertIsNone(get_psycopg2_serialization_exception(exception))

    def test__returns_psycopg2_error_root_cause(self):
        exception = Exception()
        exception.__cause__ = orm.SerializationFailure()
        self.assertIs(
            exception.__cause__,
            get_psycopg2_serialization_exception(exception))


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

    def test_retries_on_serialization_failure(self):
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

    def test_calls_reset_between_retries(self):
        reset = Mock()
        function = self.make_mock_function()
        function.side_effect = self.cause_serialization_failure
        function_wrapped = retry_on_serialization_failure(function, reset)
        self.assertRaises(OperationalError, function_wrapped)
        expected_function_calls = [call()] * 10
        self.expectThat(function, MockCallsMatch(*expected_function_calls))
        # There's one fewer reset than calls to the function.
        expected_reset_calls = expected_function_calls[:-1]
        self.expectThat(reset, MockCallsMatch(*expected_reset_calls))

    def test_does_not_call_reset_before_first_attempt(self):
        reset = Mock()
        function = self.make_mock_function()
        function.return_value = sentinel.all_is_okay
        function_wrapped = retry_on_serialization_failure(function, reset)
        function_wrapped()
        self.assertThat(reset, MockNotCalled())


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


class TestGenRetryIntervals(MAASTestCase):
    """Tests for `orm.gen_retry_intervals`."""

    def remove_jitter(self):
        # Remove the effect of randomness.
        full_jitter = self.patch(orm, "full_jitter")
        full_jitter.side_effect = lambda thing: thing

    def test__unjittered_series_begins(self):
        self.remove_jitter()
        # Get the first 10 intervals, without jitter.
        intervals = islice(orm.gen_retry_intervals(), 10)
        # Convert from seconds to milliseconds, and round.
        intervals = [int(interval * 1000) for interval in intervals]
        # They start off small, but grow rapidly to the maximum.
        self.assertThat(intervals, Equals(
            [25, 62, 156, 390, 976, 2441, 6103, 10000, 10000, 10000]))

    def test__pulls_from_exponential_series_until_maximum_is_reached(self):
        self.remove_jitter()
        # repeat() is the tail-end of the interval series.
        repeat = self.patch(orm, "repeat")
        repeat.return_value = [sentinel.end]
        maximum = randint(10, 100)
        intervals = list(orm.gen_retry_intervals(maximum=maximum))
        self.assertThat(intervals[-1], Is(sentinel.end))
        self.assertThat(intervals[:-1], AllMatch(LessThanOrEqual(maximum)))


class TestPostCommitHooks(MAASTestCase):
    """Tests for the `post_commit_hooks` singleton."""

    def test__crashes_on_enter_if_hooks_exist(self):
        hook = Deferred()
        post_commit_hooks.add(hook)
        with ExpectedException(TransactionManagementError):
            with post_commit_hooks:
                pass
        # The hook has been cancelled, but CancelledError is suppressed in
        # hooks, so we don't see it here.
        self.assertThat(hook, IsFiredDeferred())
        # The hook list is cleared so that the exception is raised only once.
        self.assertThat(post_commit_hooks.hooks, HasLength(0))

    def test__fires_hooks_on_exit_if_no_exception(self):
        self.addCleanup(post_commit_hooks.reset)
        hooks_fire = self.patch_autospec(post_commit_hooks, "fire")
        with post_commit_hooks:
            post_commit_hooks.add(Deferred())
        # Hooks are fired.
        self.assertThat(hooks_fire, MockCalledOnceWith())

    def test__resets_hooks_on_exit_if_exception(self):
        self.addCleanup(post_commit_hooks.reset)
        hooks_fire = self.patch_autospec(post_commit_hooks, "fire")
        hooks_reset = self.patch_autospec(post_commit_hooks, "reset")
        exception_type = factory.make_exception_type()
        with ExpectedException(exception_type):
            with post_commit_hooks:
                post_commit_hooks.add(Deferred())
                raise exception_type()
        # No hooks were fired; they were reset immediately.
        self.assertThat(hooks_fire, MockNotCalled())
        self.assertThat(hooks_reset, MockCalledOnceWith())


class TestPostCommit(MAASTestCase):
    """Tests for the `post_commit` function."""

    def setUp(self):
        super(TestPostCommit, self).setUp()
        self.addCleanup(post_commit_hooks.reset)

    def test__adds_Deferred_as_hook(self):
        hook = Deferred()
        hook_added = post_commit(hook)
        self.assertEqual([hook], list(post_commit_hooks.hooks))
        self.assertThat(hook_added, Is(hook))

    def test__adds_new_Deferred_as_hook_when_called_without_args(self):
        hook_added = post_commit()
        self.assertEqual([hook_added], list(post_commit_hooks.hooks))
        self.assertThat(hook_added, IsInstance(Deferred))

    def test__adds_callable_as_hook(self):
        hook = lambda arg: None
        hook_added = post_commit(hook)
        self.assertThat(post_commit_hooks.hooks, HasLength(1))
        self.assertThat(hook_added, IsInstance(Deferred))

    def test__fire_calls_back_with_None_to_Deferred_hook(self):
        hook = Deferred()
        spy = DeferredValue()
        spy.observe(hook)
        post_commit(hook)
        post_commit_hooks.fire()
        self.assertIsNone(extract_result(spy.get()))

    def test__fire_calls_back_with_None_to_new_Deferred_hook(self):
        hook_added = post_commit()
        spy = DeferredValue()
        spy.observe(hook_added)
        post_commit_hooks.fire()
        self.assertIsNone(extract_result(spy.get()))

    def test__reset_cancels_Deferred_hook(self):
        hook = Deferred()
        spy = DeferredValue()
        spy.observe(hook)
        post_commit(hook)
        post_commit_hooks.reset()
        self.assertRaises(CancelledError, extract_result, spy.get())

    def test__reset_cancels_new_Deferred_hook(self):
        hook_added = post_commit()
        spy = DeferredValue()
        spy.observe(hook_added)
        post_commit_hooks.reset()
        self.assertRaises(CancelledError, extract_result, spy.get())

    def test__fire_passes_None_to_callable_hook(self):
        hook = Mock()
        post_commit(hook)
        post_commit_hooks.fire()
        self.assertThat(hook, MockCalledOnceWith(None))

    def test__reset_passes_Failure_to_callable_hook(self):
        hook = Mock()
        post_commit(hook)
        post_commit_hooks.reset()
        self.assertThat(hook, MockCalledOnceWith(ANY))
        arg = hook.call_args[0][0]
        self.assertThat(arg, IsInstance(Failure))
        self.assertThat(arg.value, IsInstance(CancelledError))

    def test__rejects_other_hook_types(self):
        self.assertRaises(AssertionError, post_commit, sentinel.hook)


class TestPostCommitDo(MAASTestCase):
    """Tests for the `post_commit_do` function."""

    def setUp(self):
        super(TestPostCommitDo, self).setUp()
        self.addCleanup(post_commit_hooks.reset)

    def test__adds_callable_as_hook(self):
        hook = lambda arg: None
        post_commit_do(hook)
        self.assertThat(post_commit_hooks.hooks, HasLength(1))

    def test__returns_actual_hook(self):
        hook = Mock()
        hook_added = post_commit_do(hook, sentinel.foo, bar=sentinel.bar)
        self.assertThat(hook_added, IsInstance(Deferred))
        callback, errback = hook_added.callbacks.pop(0)
        # Errors are passed through; they're not passed to our hook.
        self.expectThat(errback, Equals((passthru, None, None)))
        # Our hook is set to be called via callOut.
        self.expectThat(callback, Equals(
            (callOut, (hook, sentinel.foo), {"bar": sentinel.bar})))

    def test__fire_passes_only_args_to_hook(self):
        hook = Mock()
        post_commit_do(hook, sentinel.arg, foo=sentinel.bar)
        post_commit_hooks.fire()
        self.assertThat(
            hook, MockCalledOnceWith(sentinel.arg, foo=sentinel.bar))

    def test__reset_does_not_call_hook(self):
        hook = Mock()
        post_commit_do(hook)
        post_commit_hooks.reset()
        self.assertThat(hook, MockNotCalled())

    def test__rejects_other_hook_types(self):
        self.assertRaises(AssertionError, post_commit_do, sentinel.hook)


class TestTransactional(DjangoTransactionTestCase):

    def test__exposes_original_function(self):
        function = Mock(__name__=self.getUniqueString())
        self.assertThat(orm.transactional(function).func, Is(function))

    def test__calls_function_within_transaction_then_closes_connections(self):
        close_old_connections = self.patch(orm, "close_old_connections")

        # No transaction has been entered (what Django calls an atomic
        # block), and old connections have not been closed.
        self.assertFalse(connection.in_atomic_block)
        self.assertThat(close_old_connections, MockNotCalled())

        def check_inner(*args, **kwargs):
            # In here, the transaction (`atomic`) has been started but
            # is not over, and old connections have not yet been closed.
            self.assertTrue(connection.in_atomic_block)
            self.assertThat(close_old_connections, MockNotCalled())

        function = Mock()
        function.__name__ = self.getUniqueString()
        function.side_effect = check_inner

        # Call `function` via the `transactional` decorator.
        decorated_function = orm.transactional(function)
        decorated_function(sentinel.arg, kwarg=sentinel.kwarg)

        # `function` was called -- and therefore `check_inner` too --
        # and the arguments passed correctly.
        self.assertThat(function, MockCalledOnceWith(
            sentinel.arg, kwarg=sentinel.kwarg))

        # After the decorated function has returned the transaction has
        # been exited, and old connections have been closed.
        self.assertFalse(connection.in_atomic_block)
        self.assertThat(close_old_connections, MockCalledOnceWith())

    def test__closes_connections_only_when_leaving_atomic_block(self):
        close_old_connections = self.patch(orm, "close_old_connections")

        @orm.transactional
        def inner():
            # We're inside a `transactional` context here.
            return "inner"

        @orm.transactional
        def outer():
            # We're inside a `transactional` context here too.
            # Call `inner`, thus nesting `transactional` contexts.
            return "outer > " + inner()

        self.assertEqual("outer > inner", outer())
        # Old connections have been closed only once.
        self.assertThat(close_old_connections, MockCalledOnceWith())

    def test__fires_post_commit_hooks_when_done(self):
        fire = self.patch(orm.post_commit_hooks, "fire")
        function = lambda: sentinel.something
        decorated_function = orm.transactional(function)
        self.assertIs(sentinel.something, decorated_function())
        self.assertThat(fire, MockCalledOnceWith())

    def test__crashes_if_hooks_exist_before_entering_transaction(self):
        post_commit(lambda failure: None)
        decorated_function = orm.transactional(lambda: None)
        self.assertRaises(TransactionManagementError, decorated_function)
        # The hook list is cleared so that the exception is raised only once.
        self.assertThat(post_commit_hooks.hooks, HasLength(0))

    def test__creates_post_commit_hook_savepoint_on_inner_block(self):
        hooks = post_commit_hooks.hooks

        @orm.transactional
        def inner():
            # We're inside a savepoint context here.
            self.assertThat(post_commit_hooks.hooks, Not(Is(hooks)))
            return "inner"

        @orm.transactional
        def outer():
            # We're inside a transaction here, but not yet a savepoint.
            self.assertThat(post_commit_hooks.hooks, Is(hooks))
            return "outer > " + inner()

        self.assertEqual("outer > inner", outer())


class TestTransactionalRetries(SerializationFailureTestCase):

    def test__retries_upon_serialization_failures(self):
        # No-op close_old_connections().
        self.patch(orm, "close_old_connections")

        function = Mock()
        function.__name__ = self.getUniqueString()
        function.side_effect = self.cause_serialization_failure
        decorated_function = orm.transactional(function)

        self.assertRaises(OperationalError, decorated_function)
        expected_calls = [call()] * 10
        self.assertThat(function, MockCallsMatch(*expected_calls))

    def test__resets_post_commit_hooks_when_retrying(self):
        reset = self.patch(orm.post_commit_hooks, "reset")

        function = Mock()
        function.__name__ = self.getUniqueString()
        function.side_effect = self.cause_serialization_failure
        decorated_function = orm.transactional(function)

        self.assertRaises(OperationalError, decorated_function)
        # reset() is called 9 times by retry_on_serialization_failure() then
        # once more by transactional().
        expected_reset_calls = [call()] * 10
        self.assertThat(reset, MockCallsMatch(*expected_reset_calls))


class TestSavepoint(DjangoTransactionTestCase):
    """Tests for `savepoint`."""

    def test__crashes_if_not_already_within_transaction(self):
        with ExpectedException(TransactionManagementError):
            with savepoint():
                pass

    def test__creates_savepoint_for_transaction_and_post_commit_hooks(self):
        hooks = post_commit_hooks.hooks
        with transaction.atomic():
            self.expectThat(connection.savepoint_ids, HasLength(0))
            with savepoint():
                # We're one savepoint in.
                self.assertThat(connection.savepoint_ids, HasLength(1))
                # Post-commit hooks have been saved.
                self.assertThat(post_commit_hooks.hooks, Not(Is(hooks)))
            self.expectThat(connection.savepoint_ids, HasLength(0))


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


class TestValidateInTransaction(DjangoTransactionTestCase):
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
