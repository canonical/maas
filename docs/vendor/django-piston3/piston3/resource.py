import sys
from types import MappingProxyType

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.signals import got_request_exception
from django.db.models.query import (
    QuerySet,
    RawQuerySet,
)
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseNotAllowed,
    HttpResponseServerError,
)
from django.views.debug import ExceptionReporter
from django.views.decorators.vary import vary_on_headers
import mimeparse

from .authentication import NoAuthentication
from .doc import HandlerMethod
from .emitters import Emitter
from .handler import typemapper
from .utils import (
    FormValidationError,
    HttpStatusCode,
    MimerDataException,
    coerce_put_post,
    format_error,
    rc,
    translate_mime,
)

CHALLENGE = object()


class Resource:
    """
    Resource. Create one for your URL mappings, just
    like you would with Django. Takes one argument,
    the handler. The second argument is optional, and
    is an authentication handler. If not specified,
    `NoAuthentication` will be used by default.
    """

    callmap = MappingProxyType(
        {
            "GET": "read",
            "POST": "create",
            "PUT": "update",
            "DELETE": "delete",
        }
    )

    def __init__(self, handler, authentication=None):
        if not callable(handler):
            raise AttributeError("Handler not callable.")

        self.handler = handler()
        self.csrf_exempt = getattr(self.handler, "csrf_exempt", True)

        if not authentication:
            self.authentication = (NoAuthentication(),)
        elif isinstance(authentication, list | tuple):
            self.authentication = authentication
        else:
            self.authentication = (authentication,)

        # Erroring
        self.email_errors = getattr(settings, "PISTON_EMAIL_ERRORS", True)
        self.display_errors = getattr(settings, "PISTON_DISPLAY_ERRORS", True)
        self.stream = getattr(settings, "PISTON_STREAM_OUTPUT", False)
        # Emitter selection
        self.strict_accept = getattr(
            settings, "PISTON_STRICT_ACCEPT_HANDLING", False
        )
        self.default_emitter = getattr(
            settings, "PISTON_DEFAULT_EMITTER", "json"
        )

    def determine_emitter(self, request, *args, **kwargs):
        """
        Function for determening which emitter to use
        for output. It lives here so you can easily subclass
        `Resource` in order to change how emission is detected.
        """
        try:
            return kwargs["emitter_format"]
        except KeyError:
            pass
        if "format" in request.GET:
            return request.GET.get("format")
        if mimeparse and "HTTP_ACCEPT" in request.META:
            supported_mime_types = set()
            emitter_map = {}
            for name, (klass, content_type) in Emitter.EMITTERS.items():
                content_type_without_encoding = content_type.split(";")[0]
                supported_mime_types.add(content_type_without_encoding)
                emitter_map[content_type_without_encoding] = name
            preferred_content_type = mimeparse.best_match(
                list(supported_mime_types), request.META["HTTP_ACCEPT"]
            )
            return emitter_map.get(preferred_content_type, None)

    def form_validation_response(self, e):
        """
        Method to return form validation error information.
        You will probably want to override this in your own
        `Resource` subclass.
        """
        resp = rc.BAD_REQUEST
        resp.write(f" {e.form.errors}")
        return resp

    @property
    def anonymous(self):
        """
        Gets the anonymous handler. Also tries to grab a class
        if the `anonymous` value is a string, so that we can define
        anonymous handlers that aren't defined yet (like, when
        you're subclassing your basehandler into an anonymous one.)
        """
        if hasattr(self.handler, "anonymous"):
            anon = self.handler.anonymous

            if callable(anon):
                return anon

            for klass in typemapper.keys():
                if anon == klass.__name__:
                    return klass

        return None

    def authenticate(self, request, rm):
        actor, anonymous = False, True

        for authenticator in self.authentication:
            if not authenticator.is_authenticated(request):
                if self.anonymous and rm in self.anonymous.allowed_methods:
                    actor, anonymous = self.anonymous(), True
                else:
                    actor, anonymous = authenticator.challenge, CHALLENGE
            else:
                return self.handler, self.handler.is_anonymous

        return actor, anonymous

    @vary_on_headers("Authorization")
    def __call__(self, request, *args, **kwargs):
        """
        NB: Sends a `Vary` header so we don't cache requests
        that are different (OAuth stuff in `Authorization` header.)
        """
        rm = request.method.upper()

        # Django's internal mechanism doesn't pick up
        # PUT request, so we trick it a little here.
        if rm == "PUT":
            coerce_put_post(request)

        actor, anonymous = self.authenticate(request, rm)

        if anonymous is CHALLENGE:
            return actor(request)
        else:
            handler = actor

        # Translate nested datastructs into `request.data` here.
        if rm in ("POST", "PUT"):
            try:
                translate_mime(request)
            except MimerDataException:
                return rc.BAD_REQUEST
            if not hasattr(request, "data"):
                if rm == "POST":
                    request.data = request.POST
                else:
                    request.data = request.PUT

        if rm not in handler.allowed_methods:
            return HttpResponseNotAllowed(handler.allowed_methods)

        meth = getattr(handler, self.callmap.get(rm, ""), None)
        if not meth:
            raise Http404

        # Support emitter through (?P<emitter_format>) and ?format=emitter
        # and lastly Accept: header processing
        em_format = self.determine_emitter(request, *args, **kwargs)
        if not em_format:
            request_has_accept = "HTTP_ACCEPT" in request.META
            if request_has_accept and self.strict_accept:
                return rc.NOT_ACCEPTABLE
            em_format = self.default_emitter

        kwargs.pop("emitter_format", None)

        # Clean up the request object a bit, since we might
        # very well have `oauth_`-headers in there, and we
        # don't want to pass these along to the handler.
        request = self.cleanup_request(request)

        try:
            result = meth(request, *args, **kwargs)
        except Exception as e:
            result = self.error_handler(e, request, meth, em_format)

        try:
            emitter, ct = Emitter.get(em_format)
            fields = handler.fields

            if hasattr(handler, "list_fields") and isinstance(
                result, list | tuple | QuerySet | RawQuerySet
            ):
                fields = handler.list_fields
            if callable(fields):
                fields = fields(request, *args, **kwargs)
        except ValueError:
            result = rc.BAD_REQUEST
            result.content = f"Invalid output format specified '{em_format}'."
            return result

        status_code = 200

        # If we're looking at a response object which contains non-string
        # content, then assume we should use the emitter to format that
        # content
        if self._use_emitter(result):
            status_code = result.status_code
            # Note: We can't use result.content here because that method
            # attempts to convert the content into a string which we don't
            # want. _container is the raw data
            result = result._container

        srl = emitter(result, typemapper, handler, fields, anonymous)

        try:
            """
            Decide whether or not we want a generator here,
            or we just want to buffer up the entire result
            before sending it to the client. Won't matter for
            smaller datasets, but larger will have an impact.
            """
            if self.stream:
                stream = srl.stream_render(request)
            else:
                stream = srl.render(request)

            if not isinstance(stream, HttpResponse):
                resp = HttpResponse(
                    stream, content_type=ct, status=status_code
                )
            else:
                resp = stream

            resp.streaming = self.stream

            return resp
        except HttpStatusCode as e:
            return e.response

    @staticmethod
    def _use_emitter(result):
        """True iff result is a HttpResponse and contains non-string content."""
        if not isinstance(result, HttpResponse):
            return False
        # no chance to check type of input content anymore, but responses with
        # other status codes than 200 should not contain real payload
        return result.status_code == 200

    @staticmethod
    def cleanup_request(request):
        """
        Removes `oauth_` keys from various dicts on the
        request object, and returns the sanitized version.
        """
        for method_type in ("GET", "PUT", "POST", "DELETE"):
            block = getattr(request, method_type, {})

            if True in [k.startswith("oauth_") for k in block.keys()]:
                sanitized = block.copy()

                for k in sanitized.keys():
                    if k.startswith("oauth_"):
                        sanitized.pop(k)

                setattr(request, method_type, sanitized)

        return request

    # --

    def email_exception(self, reporter):
        subject = "Piston crash report"
        html = reporter.get_traceback_html()

        message = EmailMessage(
            settings.EMAIL_SUBJECT_PREFIX + subject,
            html,
            settings.SERVER_EMAIL,
            [admin[1] for admin in settings.ADMINS],
        )

        message.content_subtype = "html"
        message.send(fail_silently=True)

    def error_handler(self, e, request, meth, em_format):
        """
        Override this method to add handling of errors customized for your
        needs
        """
        if isinstance(e, FormValidationError):
            return self.form_validation_response(e)
        got_request_exception.send(sender=type(self), request=request)
        if isinstance(e, TypeError):
            result = rc.BAD_REQUEST
            hm = HandlerMethod(meth)
            sig = hm.signature

            msg = "Method signature does not match.\n\n"

            if sig:
                msg += f"Signature should be: {sig}"
            else:
                msg += "Resource does not expect any parameters."

            if self.display_errors:
                msg += f"\n\nException was: {e!s}"

            result.content = format_error(msg)
            return result
        elif isinstance(e, Http404):
            return rc.NOT_FOUND

        elif isinstance(e, HttpStatusCode):
            return e.response

        else:
            """
            On errors (like code errors), we'd like to be able to
            give crash reports to both admins and also the calling
            user. There's two setting parameters for this:

            Parameters::
             - `PISTON_EMAIL_ERRORS`: Will send a Django formatted
               error email to people in `settings.ADMINS`.
             - `PISTON_DISPLAY_ERRORS`: Will return a simple traceback
               to the caller, so he can tell you what error they got.

            If `PISTON_DISPLAY_ERRORS` is not enabled, the caller will
            receive a basic "500 Internal Server Error" message.
            """
            exc_type, exc_value, tb = sys.exc_info()
            rep = ExceptionReporter(request, exc_type, exc_value, tb.tb_next)
            if self.email_errors:
                self.email_exception(rep)
            if self.display_errors:
                return HttpResponseServerError(rep.get_traceback_text())
            else:
                raise
