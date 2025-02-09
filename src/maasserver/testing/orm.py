# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""ORM-related test helpers."""

from contextlib import contextmanager

from django.db import transaction
import testtools

from maasserver.utils.orm import gen_description_of_hooks, post_commit_hooks


def reload_objects(model_class, model_objects):
    """Reload `model_objects` of type `model_class` from the database.

    Use this when a test needs to inspect changes to model objects made by
    the API.

    If any of the objects have been deleted, they will not be included in
    the result.

    :param model_class: `Model` class to reload from.
    :type model_class: Class.
    :param model_objects: Objects to reload from the database.
    :type model_objects: Sequence of `model_class` objects.
    :return: Reloaded objects, in no particular order.
    :rtype: Sequence of `model_class` objects.
    """
    assert all(isinstance(obj, model_class) for obj in model_objects)
    return model_class.objects.filter(id__in=[obj.id for obj in model_objects])


class PostCommitHooksTestMixin(testtools.TestCase):
    """Reset all post-commit hooks.

    This also adds an expectation to `test` that there aren't any leaking
    post-commit hooks. The test will still run, but will be marked as failed.
    The learnings: tests should not be allowing post-commit hooks to escape.
    """

    def setUp(self):
        try:
            super().setUp()
            description_of_hooks = "\n".join(
                gen_description_of_hooks(post_commit_hooks.hooks)
            )
            assert len(post_commit_hooks.hooks) == 0, (
                "One or more post-commit tasks were present before commencing this test:\n"
                + description_of_hooks
            )
        finally:
            # By this point we will have reported the leaked post-commit
            # tasks, so always reset them; we don't want to report them again,
            # and we don't want to execute them.
            post_commit_hooks.reset()

    def tearDown(self):
        try:
            description_of_hooks = "\n".join(
                gen_description_of_hooks(post_commit_hooks.hooks)
            )
            assert len(post_commit_hooks.hooks) == 0, (
                "One or more post-commit tasks were present at the end of this test:\n"
                + description_of_hooks
            )
            super().tearDown()
        finally:
            # By this point we will have reported the leaked post-commit
            # tasks, so always reset them; we don't want to report them again,
            # and we don't want to execute them.
            post_commit_hooks.reset()


@contextmanager
def rollback():
    """Context manager that always rolls back to a savepoint.

    This is useful when using hypothesis (https://hypothesis.readthedocs.org/)
    which repeatedly runs tests to discover edge cases.
    """
    sid = transaction.savepoint()
    try:
        yield
    finally:
        transaction.savepoint_rollback(sid)
