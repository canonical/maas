# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for configuration update code."""


from unittest.mock import Mock

from testtools.matchers import Equals, HasLength

from maastesting.testcase import MAASTestCase
from provisioningserver import support_dump


class TestUpdateMaasClusterConf(MAASTestCase):
    # Test to ensure that if exceptions are thrown during the dump, the dump
    # continues through all the items to dump anyway.
    scenarios = (
        ("without_exception_mock", {"exceptions": False}),
        ("with_exception_mock", {"exceptions": True}),
    )

    def setUp(self):
        super().setUp()
        self.mock_calls = 0
        self.last_args = None
        self.last_kwargs = None
        self.expected_networking = len(support_dump.NETWORKING_DUMP)
        self.expected_config = len(support_dump.CONFIG_DUMP)
        self.expected_images = len(support_dump.IMAGES_DUMP)
        for item in support_dump.NETWORKING_DUMP:
            self.substitute_mock_call(item, self.exceptions)
        for item in support_dump.CONFIG_DUMP:
            self.substitute_mock_call(item, self.exceptions)
        for item in support_dump.IMAGES_DUMP:
            self.substitute_mock_call(item, self.exceptions)

    def substitute_mock_call(self, item, with_exception):
        if with_exception:
            item["function"] = self.mock_dump_with_raise
        else:
            item["function"] = self.mock_dump

        if "command" in item:
            item["command"] = "/bin/true"

    def make_args(self, **kwargs):
        args = Mock()
        args.__dict__.update(kwargs)
        return args

    def mock_dump(self, *args, **kwargs):
        self.mock_calls += 1
        self.last_args = args
        self.last_kwargs = kwargs

    def mock_dump_with_raise(self, *args, **kwargs):
        self.mock_calls += 1
        self.last_args = args
        self.last_kwargs = kwargs
        raise Exception("Fatality.")

    def test_dump_with_no_args_dumps_everything(self):
        support_dump.run(self.make_args())
        self.assertThat(
            self.mock_calls,
            Equals(
                self.expected_config
                + self.expected_images
                + self.expected_networking
            ),
        )

    def test_dump_with_networking_arg_dumps_expected(self):
        support_dump.run(self.make_args(networking=True))
        self.assertEqual(self.expected_networking, self.mock_calls)

    def test_dump_with_config_arg_dumps_expected_functions(self):
        support_dump.run(self.make_args(config=True))
        self.assertEqual(self.expected_config, self.mock_calls)

    def test_dump_with_images_arg_dumps_expected_functions(self):
        support_dump.run(self.make_args(images=True))
        self.assertEqual(self.expected_images, self.mock_calls)

    def test_dump_with_images_preserves_args(self):
        support_dump.run(self.make_args(images=True))
        self.assertThat(self.last_args, HasLength(1))

    def test_dump_with_images_and_config_args_dumps_expected_functions(self):
        support_dump.run(self.make_args(images=True, config=True))
        self.assertEqual(
            self.expected_images + self.expected_config,
            self.mock_calls,
        )

    def test_dump_with_images_and_networking_args_dumps_expected_functions(
        self,
    ):
        support_dump.run(self.make_args(images=True, networking=True))
        self.assertEqual(
            self.expected_images + self.expected_networking,
            self.mock_calls,
        )

    def test_dump_with_networking_and_config_args_dumps_expected_functions(
        self,
    ):
        support_dump.run(self.make_args(networking=True, config=True))
        self.assertEqual(
            self.expected_networking + self.expected_config,
            self.mock_calls,
        )

    def test_dump_with_networking_and_images_args_dumps_expected_functions(
        self,
    ):
        support_dump.run(self.make_args(networking=True, images=True))
        self.assertEqual(
            self.expected_networking + self.expected_images,
            self.mock_calls,
        )

    def test_dump_with_all_args_dumps_all_functions(self):
        support_dump.run(
            self.make_args(networking=True, images=True, config=True)
        )
        self.assertThat(
            self.mock_calls,
            Equals(
                self.expected_config
                + self.expected_images
                + self.expected_networking
            ),
        )
