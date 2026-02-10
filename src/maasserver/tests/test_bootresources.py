# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from django.db import transaction
from twisted.application.internet import TimerService
from twisted.internet.defer import fail, succeed

from maasserver import bootresources
from maasserver.components import (
    get_persistent_error,
    register_persistent_error,
)
from maasserver.enum import COMPONENT
from maasserver.models import Config
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting import get_testing_timeout
from maastesting.crochet import wait_for
from maastesting.testcase import MAASTestCase
from maastesting.twisted import extract_result, TwistedLoggerFixture
from provisioningserver.utils.text import normalise_whitespace
from provisioningserver.utils.twisted import asynchronous

TIMEOUT = get_testing_timeout()
wait_for_reactor = wait_for()


class TestStopImportResources(MAASTransactionServerTestCase):
    def test_does_nothing_if_import_not_running(self):
        mock_running = self.patch(bootresources, "is_import_resources_running")
        mock_running.return_value = False
        mock_cancel_workflow = self.patch(bootresources, "cancel_workflow")
        mock_cancel_workflows_of_type = self.patch(
            bootresources, "cancel_workflows_of_type"
        )

        bootresources.stop_import_resources()

        mock_running.assert_called_once()
        mock_cancel_workflow.assert_not_called()
        mock_cancel_workflows_of_type.assert_not_called()

    def test_sends_stop_import_notification(self):
        mock_running = self.patch(bootresources, "is_import_resources_running")
        mock_running.return_value = True
        mock_cancel_workflow = self.patch(bootresources, "cancel_workflow")

        bootresources.stop_import_resources()

        mock_running.assert_called_once()
        mock_cancel_workflow.assert_called_once_with(
            workflow_id="master-image-sync"
        )


class TestImportResourcesService(MAASTestCase):
    """Tests for `ImportResourcesService`."""

    def test_is_a_TimerService(self):
        service = bootresources.ImportResourcesService()
        self.assertIsInstance(service, TimerService)

    def test_runs_once_an_hour(self):
        service = bootresources.ImportResourcesService()
        self.assertEqual(3600, service.step)

    def test_calls__maybe_import_resources(self):
        service = bootresources.ImportResourcesService()
        self.assertEqual(
            (service.maybe_import_resources, (), {}), service.call
        )

    def test_maybe_import_resources_does_not_error(self):
        retry_patch = self.patch(bootresources, "retry")
        retry_patch.return_value = succeed(None)
        service = bootresources.ImportResourcesService()
        deferToDatabase = self.patch(bootresources, "deferToDatabase")
        exception_type = factory.make_exception_type()
        deferToDatabase.return_value = fail(exception_type())
        d = service.maybe_import_resources()
        self.assertIsNone(extract_result(d))
        retry_patch.assert_any_call(service._fetch_manifest, timeout=60)


class TestImportResourcesServiceAsync(MAASTransactionServerTestCase):
    """Tests for the async parts of `ImportResourcesService`."""

    def test_imports_resources_in_thread_if_auto(self):
        self.patch(bootresources, "import_resources")
        self.patch(bootresources, "is_dev_environment").return_value = False
        self.patch(bootresources, "execute_workflow")

        with transaction.atomic():
            Config.objects.set_config("boot_images_auto_import", True)

        service = bootresources.ImportResourcesService()
        maybe_import_resources = asynchronous(service.maybe_import_resources)
        maybe_import_resources().wait(TIMEOUT)

        bootresources.import_resources.assert_called_once()

    def test_no_auto_import_if_dev(self):
        self.patch(bootresources, "import_resources")
        self.patch(bootresources, "execute_workflow")

        with transaction.atomic():
            Config.objects.set_config("boot_images_auto_import", True)

        service = bootresources.ImportResourcesService()
        maybe_import_resources = asynchronous(service.maybe_import_resources)
        maybe_import_resources().wait(TIMEOUT)

        bootresources.import_resources.assert_not_called()

    def test_does_not_import_resources_in_thread_if_not_auto(self):
        self.patch(bootresources, "import_resources")
        self.patch(bootresources, "execute_workflow")

        with transaction.atomic():
            Config.objects.set_config("boot_images_auto_import", False)

        service = bootresources.ImportResourcesService()
        maybe_import_resources = asynchronous(service.maybe_import_resources)
        maybe_import_resources().wait(TIMEOUT)

        bootresources.import_resources.assert_not_called()

    def test_maybe_import_resources_logs_errback_on_failure(self):
        self.patch(bootresources, "execute_workflow")
        with transaction.atomic():
            Config.objects.set_config("boot_images_auto_import", True)

        service = bootresources.ImportResourcesService()

        retry_patch = self.patch(bootresources, "retry")
        retry_patch.return_value = fail(Exception("BOOM"))
        log_mock = self.patch(bootresources.log, "err")

        maybe_import_resources = asynchronous(service.maybe_import_resources)
        maybe_import_resources().wait(TIMEOUT)

        log_mock.assert_called()
        called_message = log_mock.call_args[0][1]
        expected_message = "Failure importing boot resources. Next automatic retry will be triggered in 1:00:00 hours."
        self.assertEqual(called_message, expected_message)


class TestImportResourcesProgressService(MAASServerTestCase):
    """Tests for `ImportResourcesProgressService`."""

    def test_is_a_TimerService(self):
        service = bootresources.ImportResourcesProgressService()
        self.assertIsInstance(service, TimerService)

    def test_runs_every_three_minutes(self):
        service = bootresources.ImportResourcesProgressService()
        self.assertEqual(180, service.step)

    def test_calls_try_check_boot_images(self):
        service = bootresources.ImportResourcesProgressService()
        func, args, kwargs = service.call
        self.assertEqual(func, service.try_check_boot_images)
        self.assertEqual(args, ())
        self.assertEqual(kwargs, {})


class TestImportResourcesProgressServiceAsync(MAASTransactionServerTestCase):
    """Tests for the async parts of `ImportResourcesProgressService`."""

    def set_maas_url(self):
        maas_url_path = "/path/%s" % factory.make_string()
        maas_url = factory.make_simple_http_url(path=maas_url_path)
        self.useFixture(RegionConfigurationFixture(maas_url=maas_url))
        return maas_url, maas_url_path

    def patch_are_functions(self, service, region_answer):
        # Patch the are_boot_images_available_* functions.
        are_region_func = self.patch_autospec(
            service, "are_boot_images_available_in_the_region"
        )
        are_region_func.return_value = region_answer

    def test_adds_warning_if_boot_image_import_not_started(self):
        maas_url, maas_url_path = self.set_maas_url()

        service = bootresources.ImportResourcesProgressService()
        self.patch_are_functions(service, False)

        check_boot_images = asynchronous(service.check_boot_images)
        check_boot_images().wait(TIMEOUT)

        error_observed = get_persistent_error(COMPONENT.IMPORT_PXE_FILES)
        error_expected = """\
        Boot image import process not started. Machines will not be able to
        provision without boot images. Visit the <a href="/MAAS/r/images">boot images</a>
        page to start the import.
        """
        self.assertEqual(
            normalise_whitespace(error_expected),
            normalise_whitespace(error_observed),
        )

    def test_removes_warning_if_boot_image_process_started(self):
        register_persistent_error(
            COMPONENT.IMPORT_PXE_FILES,
            "You rotten swine, you! You have deaded me!",
        )

        service = bootresources.ImportResourcesProgressService()
        self.patch_are_functions(service, True)

        check_boot_images = asynchronous(service.check_boot_images)
        check_boot_images().wait(TIMEOUT)

        error = get_persistent_error(COMPONENT.IMPORT_PXE_FILES)
        self.assertIsNone(error)

    def test_logs_all_errors(self):
        logger = self.useFixture(TwistedLoggerFixture())

        exception = factory.make_exception()
        service = bootresources.ImportResourcesProgressService()
        check_boot_images = self.patch_autospec(service, "check_boot_images")
        check_boot_images.return_value = fail(exception)
        try_check_boot_images = asynchronous(service.try_check_boot_images)
        try_check_boot_images().wait(TIMEOUT)

        self.assertEqual(
            [
                "Failure checking for boot images.",
                "Traceback (most recent call last):",
                f"Failure: maastesting.factory.{type(exception).__name__}: ",
            ],
            logger.output.splitlines(),
        )

    def test_are_boot_images_available_in_the_region(self):
        service = bootresources.ImportResourcesProgressService()
        self.assertFalse(service.are_boot_images_available_in_the_region())
        factory.make_BootResource()
        self.assertTrue(service.are_boot_images_available_in_the_region())
