import secrets
import string
import time
from types import MappingProxyType
from typing import ClassVar

from django import get_version as django_version
from django.conf import settings
from django.core.cache import cache
from django.core.mail import (
    mail_admins,
    send_mail,
)
from django.http import HttpResponse
from django.template import (
    TemplateDoesNotExist,
    loader,
)
from django.utils.translation import gettext as _

from .decorator import decorator

__version__ = "0.2.3rc1"


def get_version():
    return __version__


def format_error(error):
    return f"Piston/{get_version()} (Django {django_version()}) crash report:\n\n{error}"


class rc_factory:
    """
    Status codes.
    """

    CODES = MappingProxyType(
        dict(
            ALL_OK=("OK", 200),
            CREATED=("Created", 201),
            ACCEPTED=("Accepted", 202),
            DELETED=("", 204),  # 204 says "Don't send a body!"
            BAD_REQUEST=("Bad Request", 400),
            FORBIDDEN=("Forbidden", 401),
            NOT_FOUND=("Not Found", 404),
            NOT_ACCEPTABLE=("Not acceptable", 406),
            DUPLICATE_ENTRY=("Conflict/Duplicate", 409),
            NOT_HERE=("Gone", 410),
            INTERNAL_ERROR=("Internal Error", 500),
            NOT_IMPLEMENTED=("Not Implemented", 501),
            THROTTLED=("Throttled", 503),
        )
    )

    def __getattr__(self, attr):
        """
        Returns a fresh `HttpResponse` when getting
        an "attribute". This is backwards compatible
        with 0.2, which is important.
        """
        try:
            (r, c) = self.CODES.get(attr)
        except TypeError:
            raise AttributeError(attr)

        return HttpResponse(r, content_type="text/plain", status=c)


rc = rc_factory()


class FormValidationError(Exception):
    def __init__(self, form):
        self.form = form


class HttpStatusCode(Exception):
    def __init__(self, response):
        self.response = response


def validate(v_form, operation="POST"):
    @decorator
    def wrap(f, self, request, *a, **kwa):
        form = v_form(getattr(request, operation), request.FILES)

        if form.is_valid():
            setattr(request, "form", form)
            return f(self, request, *a, **kwa)
        else:
            raise FormValidationError(form)

    return wrap


def throttle(max_requests, timeout=60 * 60, extra=""):
    """
    Simple throttling decorator, caches
    the amount of requests made in cache.

    If used on a view where users are required to
    log in, the username is used, otherwise the
    IP address of the originating request is used.

    Parameters::
     - `max_requests`: The maximum number of requests
     - `timeout`: The timeout for the cache entry (default: 1 hour)
    """

    @decorator
    def wrap(f, self, request, *args, **kwargs):
        if request.user.is_authenticated():
            ident = request.user.username
        else:
            ident = request.META.get("REMOTE_ADDR", None)

        if hasattr(request, "throttle_extra"):
            """
            Since we want to be able to throttle on a per-
            application basis, it's important that we realize
            that `throttle_extra` might be set on the request
            object. If so, append the identifier name with it.
            """
            ident += f":{request.throttle_extra!s}"

        if ident:
            """
            Preferrably we'd use incr/decr here, since they're
            atomic in memcached, but it's in django-trunk so we
            can't use it yet. If someone sees this after it's in
            stable, you can change it here.
            """
            ident += f":{extra}"

            now = time.time()
            count, expiration = cache.get(ident, (1, None))

            if expiration is None:
                expiration = now + timeout

            if count >= max_requests and expiration > now:
                t = rc.THROTTLED
                wait = int(expiration - now)
                t.content = "Throttled, wait %d seconds." % wait
                t["Retry-After"] = wait
                return t

            cache.set(ident, (count + 1, expiration), (expiration - now))

        return f(self, request, *args, **kwargs)

    return wrap


def coerce_put_post(request):
    """
    Django doesn't particularly understand REST.
    In case we send data over PUT, Django won't
    actually look at the data and load it. We need
    to twist its arm here.

    The try/except abominiation here is due to a bug
    in mod_python. This should fix it.
    """
    if request.method == "PUT":
        # Bug fix: if _load_post_and_files has already been called, for
        # example by middleware accessing request.POST, the below code to
        # pretend the request is a POST instead of a PUT will be too late
        # to make a difference. Also calling _load_post_and_files will result
        # in the following exception:
        #   AttributeError: You cannot set the upload handlers after the upload has been processed.
        # The fix is to check for the presence of the _post field which is set
        # the first time _load_post_and_files is called (both by wsgi.py and
        # modpython.py). If it's set, the request has to be 'reset' to redo
        # the query value parsing in POST mode.
        if hasattr(request, "_post"):
            del request._post
            del request._files

        try:
            request.method = "POST"
            request._load_post_and_files()
            request.method = "PUT"
        except AttributeError:
            request.META["REQUEST_METHOD"] = "POST"
            request._load_post_and_files()
            request.META["REQUEST_METHOD"] = "PUT"

        request.PUT = request.POST


class MimerDataException(Exception):
    """
    Raised if the content_type and data don't match
    """

    pass


class Mimer:
    TYPES: ClassVar[dict] = dict()

    def __init__(self, request):
        self.request = request

    def is_multipart(self):
        content_type = self.content_type()

        if content_type is not None:
            return content_type.lstrip().startswith("multipart")

        return False

    def loader_for_type(self, ctype):
        """
        Gets a function ref to deserialize content
        for a certain mimetype.
        """
        for loadee, mimes in Mimer.TYPES.items():
            for mime in mimes:
                if ctype.startswith(mime):
                    return loadee

    def content_type(self):
        """
        Returns the content type of the request in all cases where it is
        different than a submitted form - application/x-www-form-urlencoded
        """
        type_formencoded = "application/x-www-form-urlencoded"

        ctype = self.request.META.get("CONTENT_TYPE", type_formencoded)

        if type_formencoded in ctype:
            return None

        return ctype

    def translate(self):
        """
        Will look at the `Content-type` sent by the client, and maybe
        deserialize the contents into the format they sent. This will
        work for JSON, YAML, XML and Pickle. Since the data is not just
        key-value (and maybe just a list), the data will be placed on
        `request.data` instead, and the handler will have to read from
        there.

        It will also set `request.piston_content_type` so the handler has an
        easy way to tell what's going on. `request.piston_content_type` will
        always be None for form-encoded and/or multipart form data
        (what your browser sends.)
        """
        ctype = self.content_type()
        self.request.piston_content_type = ctype

        if not self.is_multipart() and ctype:
            loadee = self.loader_for_type(ctype)

            if loadee:
                try:
                    data = self.request.body
                    # PY3: Loaders usually don't work with bytes:
                    data = data.decode("utf-8")
                    self.request.data = loadee(data)

                    # Reset both POST and PUT from request, as its
                    # misleading having their presence around.
                    self.request.POST = self.request.PUT = dict()
                except (TypeError, ValueError):
                    # This also catches if loadee is None.
                    raise MimerDataException
            else:
                self.request.data = None

        return self.request

    @classmethod
    def register(cls, loadee, types):
        cls.TYPES[loadee] = types

    @classmethod
    def unregister(cls, loadee):
        return cls.TYPES.pop(loadee)


def translate_mime(request):
    request = Mimer(request).translate()


def require_mime(*mimes):
    """
    Decorator requiring a certain mimetype. There's a nifty
    helper called `require_extended` below which requires everything
    we support except for post-data via form.
    """

    @decorator
    def wrap(f, self, request, *args, **kwargs):
        m = Mimer(request)
        realmimes = set()

        rewrite = {
            "json": "application/json",
            "yaml": "application/x-yaml",
            "xml": "text/xml",
            "pickle": "application/python-pickle",
        }

        for idx, mime in enumerate(mimes):
            realmimes.add(rewrite.get(mime, mime))

        if not m.content_type() in realmimes:
            return rc.BAD_REQUEST

        return f(self, request, *args, **kwargs)

    return wrap


require_extended = require_mime("json", "yaml", "xml", "pickle")


def send_consumer_mail(consumer):
    """
    Send a consumer an email depending on what their status is.
    """
    try:
        subject = settings.PISTON_OAUTH_EMAIL_SUBJECTS[consumer.status]
    except AttributeError:
        # Import Site late to avoid depending on Django configuration
        # for the rest of the code.
        from django.contrib.sites.models import Site

        subject = f"Your API Consumer for {Site.objects.get_current().name} "
        if consumer.status == "accepted":
            subject += "was accepted!"
        elif consumer.status == "canceled":
            subject += "has been canceled."
        elif consumer.status == "rejected":
            subject += "has been rejected."
        else:
            subject += "is awaiting approval."

    template = f"piston/mails/consumer_{consumer.status}.txt"

    try:
        body = loader.render_to_string(
            template, {"consumer": consumer, "user": consumer.user}
        )
    except TemplateDoesNotExist:
        """
        They haven't set up the templates, which means they might not want
        these emails sent.
        """
        return

    try:
        sender = settings.PISTON_FROM_EMAIL
    except AttributeError:
        sender = settings.DEFAULT_FROM_EMAIL

    if consumer.user:
        send_mail(
            _(subject), body, sender, [consumer.user.email], fail_silently=True
        )

    if consumer.status == "pending" and len(settings.ADMINS):
        mail_admins(_(subject), body, fail_silently=True)

    if settings.DEBUG and consumer.user:
        print(f"Mail being sent, to={consumer.user.email}")
        print(f"Subject: {_(subject)}")
        print(body)


def make_random_password(length: int) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for i in range(length))
