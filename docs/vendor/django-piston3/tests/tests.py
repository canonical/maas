from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.http import (
    HttpRequest,
    HttpResponse,
)
from django.template import (
    TemplateDoesNotExist,
    loader,
)

from piston3.handler import BaseHandler
from piston3.models import Consumer
from piston3.resource import Resource
from piston3.test import TestCase
from piston3.utils import rc


def make_request(method="GET"):
    request = HttpRequest()
    request.method = method
    request.META.update({"SERVER_NAME": "example.com", "SERVER_PORT": 80})
    return request


class ConsumerTest(TestCase):
    fixtures = ("models.json",)

    def setUp(self):
        self.consumer = Consumer()
        self.consumer.name = "Piston Test Consumer"
        self.consumer.description = "A test consumer for Piston."
        self.consumer.user = User.objects.get(pk=3)
        self.consumer.generate_random_codes()

    def _pre_test_email(self):
        template = f"piston/mails/consumer_{self.consumer.status}.txt"
        try:
            loader.render_to_string(
                template,
                {"consumer": self.consumer, "user": self.consumer.user},
            )
            return True
        except TemplateDoesNotExist:
            """
            They haven't set up the templates, which means they might not want
            these emails sent.
            """
            return False

    def test_create_pending(self):
        """Ensure creating a pending Consumer sends proper emails"""
        # Verify if the emails can be sent
        if not self._pre_test_email():
            return

        # If it's pending we should have two messages in the outbox; one
        # to the consumer and one to the site admins.
        if len(settings.ADMINS):
            self.assertEqual(len(mail.outbox), 2)
        else:
            self.assertEqual(len(mail.outbox), 1)

        expected = "Your API Consumer for example.com is awaiting approval."
        self.assertEqual(mail.outbox[0].subject, expected)

    def test_delete_consumer(self):
        """Ensure deleting a Consumer sends a cancel email"""

        # Clear out the outbox before we test for the cancel email.
        mail.outbox = []

        # Delete the consumer, which should fire off the cancel email.
        self.consumer.delete()

        # Verify if the emails can be sent
        if not self._pre_test_email():
            return

        self.assertEqual(len(mail.outbox), 1)
        expected = "Your API Consumer for example.com has been canceled."
        self.assertEqual(mail.outbox[0].subject, expected)


class ErrorHandlerTest(TestCase):
    def test_customized_error_handler(self):
        """
        Throw a custom error from a handler method and catch (and format) it
        in an overridden error_handler method on the associated Resource object
        """

        class GoAwayError(Exception):
            def __init__(self, name, reason):
                self.name = name
                self.reason = reason

        class MyHandler(BaseHandler):
            """
            Handler which raises a custom exception
            """

            allowed_methods = ("GET",)

            def read(self, request):
                raise GoAwayError("Jerome", "No one likes you")

        class MyResource(Resource):
            def error_handler(self, error, request, meth, em_format):
                # if the exception is our exeption then generate a
                # custom response with embedded content that will be
                # formatted as json
                if isinstance(error, GoAwayError):
                    response = rc.FORBIDDEN
                    response.content = b"error"
                    return response

                return super().error_handler(error, request, meth)

        resource = MyResource(MyHandler)

        request = make_request()
        response = resource(request, emitter_format="json")

        self.assertEqual(401, response.status_code)
        self.assertEqual(response.content, b"error")

    def test_type_error(self):
        """
        Verify that type errors thrown from a handler method result in a valid
        HttpResonse object being returned from the error_handler method
        """

        class MyHandler(BaseHandler):
            def read(self, request):
                raise TypeError()

        request = make_request()
        response = Resource(MyHandler)(request)

        self.assertTrue(
            isinstance(response, HttpResponse),
            f"Expected a response, not: {response}",
        )

    def test_other_error(self):
        """
        Verify that other exceptions thrown from a handler method result in a valid
        HttpResponse object being returned from the error_handler method
        """

        class MyHandler(BaseHandler):
            def read(self, request):
                raise Exception()

        resource = Resource(MyHandler)
        resource.display_errors = True
        resource.email_errors = False

        request = make_request()
        response = resource(request)

        self.assertTrue(
            isinstance(response, HttpResponse),
            f"Expected a response, not: {response}",
        )
