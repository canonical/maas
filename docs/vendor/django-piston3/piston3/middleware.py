from django.middleware.common import CommonMiddleware
from django.middleware.http import ConditionalGetMiddleware


def compat_middleware_factory(klass):
    """
    Class wrapper that only executes `process_response`
    if `streaming` is not set on the `HttpResponse` object.
    Django has a bad habbit of looking at the content,
    which will prematurely exhaust the data source if we're
    using generators or buffers.
    """

    class compatwrapper(klass):
        def process_response(self, req, resp):
            if not hasattr(resp, "streaming"):
                return klass.process_response(self, req, resp)
            return resp

    return compatwrapper


ConditionalMiddlewareCompatProxy = compat_middleware_factory(
    ConditionalGetMiddleware
)
CommonMiddlewareCompatProxy = compat_middleware_factory(CommonMiddleware)
