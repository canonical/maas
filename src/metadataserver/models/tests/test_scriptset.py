# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = []

import random

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestSetResult(MAASServerTestCase):
    """Test the ScriptSet model."""

    def test_find_script_result_by_id(self):
        script_set = factory.make_ScriptSet()
        script_results = [
            factory.make_ScriptResult(script_set=script_set)
            for _ in range(3)
        ]
        script_result = random.choice(script_results)
        self.assertEquals(
            script_result,
            script_set.find_script_result(script_result_id=script_result.id))

    def test_find_script_result_by_name(self):
        script_set = factory.make_ScriptSet()
        script_results = [
            factory.make_ScriptResult(script_set=script_set)
            for _ in range(3)
        ]
        script_result = random.choice(script_results)
        self.assertEquals(
            script_result,
            script_set.find_script_result(script_name=script_result.name))

    def test_find_script_result_returns_none_when_not_found(self):
        script_set = factory.make_ScriptSet()
        self.assertIsNone(script_set.find_script_result())
